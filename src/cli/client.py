"""Command line client for Document Search API."""

import click
import requests
import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn
from tabulate import tabulate
from datetime import datetime
import sys

console = Console()


class DocumentSearchClient:
    """Client for interacting with Document Search API."""
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        """Initialize the client with API base URL."""
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'DocumentSearchClient/1.0'
        })
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make HTTP request to the API."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(method, url, **kwargs)
            
            if response.status_code == 200:
                return response.json()
            else:
                error_data = response.json() if response.text else {}
                raise requests.HTTPError(
                    f"HTTP {response.status_code}: {error_data.get('message', 'Unknown error')}"
                )
                
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"Unable to connect to API at {self.base_url}")
        except requests.exceptions.Timeout:
            raise TimeoutError("Request timed out")
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON response from API")
    
    def health_check(self) -> dict:
        """Check API health status."""
        return self._make_request('GET', '/')
    
    def get_status(self) -> dict:
        """Get service status information."""
        return self._make_request('GET', '/status')
    
    def search_documents(self, query: str, size: int = 10, from_: int = 0) -> dict:
        """Search documents."""
        params = {'q': query, 'size': size, 'from': from_}
        return self._make_request('GET', '/search', params=params)
    
    def process_all_documents(self, max_workers: int = 5) -> dict:
        """Process all documents from S3."""
        data = {'max_workers': max_workers}
        return self._make_request('POST', '/documents/process', json=data)
    
    def sync_documents(self) -> dict:
        """Synchronize search index with S3."""
        return self._make_request('POST', '/documents/sync')
    
    def process_single_document(self, s3_key: str) -> dict:
        """Process a single document."""
        return self._make_request('POST', f'/documents/{s3_key}')
    
    def delete_document(self, s3_key: str) -> dict:
        """Delete a document from search index."""
        return self._make_request('DELETE', f'/documents/{s3_key}')


def create_results_table(documents: list) -> Table:
    """Create a rich table for search results."""
    table = Table(title="Search Results")
    
    table.add_column("File Name", style="cyan", no_wrap=True)
    table.add_column("Extension", style="magenta")
    table.add_column("Size", justify="right", style="green")
    table.add_column("Score", justify="right", style="yellow")
    table.add_column("Last Modified", style="blue")
    
    for doc in documents:
        # Format file size
        size_bytes = doc.get('size_bytes', 0)
        if size_bytes < 1024:
            size_str = f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            size_str = f"{size_bytes / 1024:.1f} KB"
        else:
            size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
        
        table.add_row(
            doc.get('file_name', 'N/A'),
            doc.get('file_extension', 'N/A'),
            size_str,
            f"{doc.get('score', 0):.2f}",
            doc.get('last_modified', 'N/A')[:10]  # Just the date part
        )
    
    return table


@click.group()
@click.option('--api-url', default='http://localhost:5000', 
              help='API base URL (default: http://localhost:5000)')
@click.pass_context
def cli(ctx, api_url):
    """Document Search CLI - Search documents stored in AWS S3."""
    ctx.ensure_object(dict)
    ctx.obj['client'] = DocumentSearchClient(api_url)
    
    # Test connection
    try:
        health = ctx.obj['client'].health_check()
        if health.get('status') != 'healthy':
            console.print("[red]Warning: API health check failed[/red]")
    except Exception as e:
        console.print(f"[red]Error connecting to API: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.pass_context
def status(ctx):
    """Show service status and statistics."""
    client = ctx.obj['client']
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Getting service status...", total=None)
            status_data = client.get_status()
            progress.remove_task(task)
        
        # Display general status
        console.print(Panel(
            f"Status: [green]{status_data.get('status', 'Unknown')}[/green]\n"
            f"Timestamp: {status_data.get('timestamp', 'N/A')}",
            title="Service Status"
        ))
        
        # Display service info
        service_info = status_data.get('service_info', {})
        
        if 's3_bucket' in service_info:
            s3_info = service_info['s3_bucket']
            console.print(Panel(
                f"Bucket: {s3_info.get('name', 'N/A')}\n"
                f"Region: {s3_info.get('region', 'N/A')}\n"
                f"Total Objects: {s3_info.get('total_objects', 0):,}\n"
                f"Total Size: {s3_info.get('total_size_mb', 0):.2f} MB",
                title="S3 Bucket Info"
            ))
        
        if 'search_index' in service_info:
            index_info = service_info['search_index']
            console.print(Panel(
                f"Index: {index_info.get('name', 'N/A')}\n"
                f"Documents: {index_info.get('document_count', 0):,}\n"
                f"Size: {index_info.get('index_size_mb', 0):.2f} MB",
                title="Search Index Info"
            ))
        
        if 'supported_extensions' in service_info:
            extensions = ', '.join(service_info['supported_extensions'])
            console.print(Panel(
                f"Extensions: {extensions}\n"
                f"Max File Size: {service_info.get('max_file_size_mb', 0)} MB",
                title="Configuration"
            ))
            
    except Exception as e:
        console.print(f"[red]Error getting status: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument('query')
@click.option('--size', '-s', default=10, help='Number of results to return (max 100)')
@click.option('--from', 'from_', default=0, help='Starting offset for pagination')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json', 'simple']), 
              default='table', help='Output format')
@click.pass_context
def search(ctx, query, size, from_, output_format):
    """Search documents by content or filename."""
    client = ctx.obj['client']
    
    if not query.strip():
        console.print("[red]Error: Search query cannot be empty[/red]")
        sys.exit(1)
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"Searching for '{query}'...", total=None)
            results = client.search_documents(query, size, from_)
            progress.remove_task(task)
        
        documents = results.get('documents', [])
        total_results = results.get('total_results', 0)
        
        if not documents:
            console.print(f"[yellow]No documents found matching '{query}'[/yellow]")
            return
        
        # Display results based on format
        if output_format == 'json':
            console.print(json.dumps(results, indent=2))
        
        elif output_format == 'simple':
            console.print(f"Found {total_results} total results, showing {len(documents)}:")
            for i, doc in enumerate(documents, 1):
                console.print(f"{i}. {doc['file_name']} (Score: {doc['score']:.2f})")
                if doc.get('url'):
                    console.print(f"   URL: {doc['url']}")
                console.print()
        
        else:  # table format
            console.print(f"\n[bold]Found {total_results} total results, showing {len(documents)}[/bold]")
            table = create_results_table(documents)
            console.print(table)
            
            # Show URLs if requested
            console.print("\n[bold]File URLs:[/bold]")
            for i, doc in enumerate(documents, 1):
                if doc.get('url'):
                    console.print(f"{i}. {doc['file_name']}: {doc['url']}")
                    
    except Exception as e:
        console.print(f"[red]Error searching: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--workers', '-w', default=5, 
              help='Number of parallel workers (default: 5, max: 20)')
@click.pass_context
def process(ctx, workers):
    """Process all documents from S3 and index them."""
    client = ctx.obj['client']
    
    if workers < 1 or workers > 20:
        console.print("[red]Error: Workers must be between 1 and 20[/red]")
        sys.exit(1)
    
    try:
        console.print(f"[blue]Starting document processing with {workers} workers...[/blue]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Processing documents...", total=None)
            results = client.process_all_documents(workers)
            progress.remove_task(task)
        
        # Display results
        processing_results = results.get('results', {})
        console.print(Panel(
            f"Total Documents: {processing_results.get('total_documents', 0)}\n"
            f"Processed: [green]{processing_results.get('processed', 0)}[/green]\n"
            f"Failed: [red]{processing_results.get('failed', 0)}[/red]\n"
            f"Skipped: [yellow]{processing_results.get('skipped', 0)}[/yellow]",
            title="Processing Results"
        ))
        
        # Show failed documents if any
        failed_docs = [r for r in processing_results.get('results', []) if not r.get('success')]
        if failed_docs:
            console.print("\n[red]Failed documents:[/red]")
            for doc in failed_docs[:10]:  # Show first 10 failures
                console.print(f"  - {doc.get('s3_key', 'Unknown')}: {doc.get('message', 'Unknown error')}")
            
            if len(failed_docs) > 10:
                console.print(f"  ... and {len(failed_docs) - 10} more")
                
    except Exception as e:
        console.print(f"[red]Error processing documents: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.pass_context
def sync(ctx):
    """Synchronize search index with S3 bucket."""
    client = ctx.obj['client']
    
    try:
        console.print("[blue]Starting synchronization with S3...[/blue]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Synchronizing...", total=None)
            results = client.sync_documents()
            progress.remove_task(task)
        
        # Display results
        sync_results = results.get('results', {})
        console.print(Panel(
            f"S3 Documents: {sync_results.get('total_s3_documents', 0)}\n"
            f"Indexed Documents: {sync_results.get('total_indexed_documents', 0)}\n"
            f"Added: [green]{sync_results.get('documents_added', 0)}[/green]\n"
            f"Removed: [red]{sync_results.get('documents_removed', 0)}[/red]\n"
            f"Completed: {sync_results.get('sync_completed_at', 'N/A')}",
            title="Synchronization Results"
        ))
        
    except Exception as e:
        console.print(f"[red]Error synchronizing: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument('s3_key')
@click.pass_context
def process_single(ctx, s3_key):
    """Process a single document by S3 key."""
    client = ctx.obj['client']
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"Processing {s3_key}...", total=None)
            result = client.process_single_document(s3_key)
            progress.remove_task(task)
        
        if result.get('success'):
            console.print(f"[green]Successfully processed: {s3_key}[/green]")
            console.print(f"Details: {result.get('details', 'N/A')}")
        else:
            console.print(f"[red]Failed to process: {s3_key}[/red]")
            console.print(f"Error: {result.get('details', 'Unknown error')}")
            
    except Exception as e:
        console.print(f"[red]Error processing document: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument('s3_key')
@click.pass_context
def delete(ctx, s3_key):
    """Delete a document from the search index."""
    client = ctx.obj['client']
    
    try:
        result = client.delete_document(s3_key)
        console.print(f"[green]Successfully deleted from search index: {s3_key}[/green]")
        
    except Exception as e:
        console.print(f"[red]Error deleting document: {e}[/red]")
        sys.exit(1)


if __name__ == '__main__':
    cli() 