#!/usr/bin/env python3
"""
MCP Server wrapper for single-file binary
Provides web fetching capabilities to Claude Code using the single-file tool
"""

import asyncio
import json
import logging
import subprocess
import sys
import tempfile
import os
import re
from pathlib import Path
from typing import Any, Sequence

import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio

try:
    import trafilatura
    HAS_TRAFILATURA = True
except ImportError:
    HAS_TRAFILATURA = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("single-file-mcp")

def estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 characters per token for most text"""
    return len(text) // 4

def paginate_content(content: str, offset: int = 0, limit: int = None) -> tuple[str, dict]:
    """Paginate content using offset/limit like the Read tool"""
    total_chars = len(content)
    
    # Apply offset
    if offset >= total_chars:
        return "", {"total_chars": total_chars, "offset": offset, "limit": limit, "returned_chars": 0}
    
    content = content[offset:]
    
    # Apply limit
    if limit is not None and limit > 0:
        content = content[:limit]
    
    returned_chars = len(content)
    
    pagination_info = {
        "total_chars": total_chars,
        "offset": offset,
        "limit": limit,
        "returned_chars": returned_chars,
        "has_more": offset + returned_chars < total_chars
    }
    
    return content, pagination_info

def truncate_content(content: str, max_tokens: int, method: str = "truncate") -> tuple[str, bool]:
    """Truncate content to fit within token limit"""
    estimated_tokens = estimate_tokens(content)
    was_truncated = False
    
    if estimated_tokens <= max_tokens:
        return content, was_truncated
    
    # Calculate target character count (reserve some tokens for metadata)
    target_chars = (max_tokens - 500) * 4  # Reserve ~500 tokens for metadata/formatting
    
    if method == "summary":
        # For summary method, take beginning and end with indicator
        if target_chars > 1000:
            prefix_chars = target_chars // 2
            suffix_chars = target_chars - prefix_chars - 200  # Reserve chars for truncation message
            
            prefix = content[:prefix_chars]
            suffix = content[-suffix_chars:] if suffix_chars > 0 else ""
            
            truncation_msg = f"\n\n[... Content truncated - showing first {prefix_chars} and last {suffix_chars} characters of {len(content)} total characters ...]\n\n"
            
            content = prefix + truncation_msg + suffix
            was_truncated = True
        else:
            # If target is too small, just truncate
            content = content[:target_chars] + "\n\n[... Content truncated ...]"
            was_truncated = True
    else:
        # Simple truncation
        content = content[:target_chars] + "\n\n[... Content truncated ...]"
        was_truncated = True
    
    return content, was_truncated

def extract_content_and_metadata(html_content: str, extract_content: bool, include_metadata: bool) -> dict:
    """Extract content and metadata from HTML using trafilatura"""
    if not HAS_TRAFILATURA:
        return {
            "content": html_content if extract_content else "",
            "metadata": {"error": "trafilatura not available"},
            "raw_html": html_content
        }
    
    result = {
        "content": "",
        "metadata": {},
        "raw_html": html_content if not extract_content else ""
    }
    
    if extract_content:
        # Extract main content as markdown-like text
        content = trafilatura.extract(
            html_content,
            output_format='markdown',
            include_comments=False,
            include_tables=True,
            include_links=True
        )
        result["content"] = content or ""
    
    if include_metadata:
        # Extract metadata
        metadata = trafilatura.extract_metadata(html_content)
        if metadata:
            result["metadata"] = {
                "title": metadata.title or "",
                "author": metadata.author or "",
                "date": metadata.date or "",
                "description": metadata.description or "",
                "sitename": metadata.sitename or "",
                "categories": metadata.categories or [],
                "tags": metadata.tags or [],
                "language": metadata.language or "",
                "url": metadata.url or ""
            }
    
    return result

# Create the MCP server
server = Server("single-file-mcp")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="fetch_webpage",
            description="Fetch a webpage and save it as a single HTML file using single-file",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL of the webpage to fetch",
                    },
                    "output_content": {
                        "type": "boolean",
                        "description": "Whether to return the HTML content in the response",
                        "default": True
                    },
                    "block_images": {
                        "type": "boolean", 
                        "description": "Block images from being downloaded",
                        "default": False
                    },
                    "block_scripts": {
                        "type": "boolean",
                        "description": "Block scripts from being downloaded", 
                        "default": True
                    },
                    "compress_html": {
                        "type": "boolean",
                        "description": "Compress the HTML output",
                        "default": True
                    },
                    "extract_content": {
                        "type": "boolean",
                        "description": "Extract main content as readable text (markdown-like format)",
                        "default": False
                    },
                    "include_metadata": {
                        "type": "boolean", 
                        "description": "Include page metadata (title, description, etc.)",
                        "default": True
                    },
                    "max_tokens": {
                        "type": "number",
                        "description": "Maximum tokens in response (default: 20000, max: 25000)",
                        "default": 20000
                    },
                    "truncate_method": {
                        "type": "string",
                        "description": "How to handle content exceeding max_tokens: 'truncate' or 'summary'",
                        "enum": ["truncate", "summary"],
                        "default": "truncate"
                    },
                    "offset": {
                        "type": "number",
                        "description": "Character offset to start reading from (for pagination)",
                        "default": 0
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of characters to return (for pagination)"
                    }
                },
                "required": ["url"],
            },
        ),
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any] | None
) -> list[types.TextContent]:
    """Handle tool calls."""
    if name != "fetch_webpage":
        raise ValueError(f"Unknown tool: {name}")

    if not arguments:
        raise ValueError("Missing arguments")

    url = arguments.get("url")
    if not url:
        raise ValueError("Missing required argument: url")

    output_content = arguments.get("output_content", True)
    block_images = arguments.get("block_images", False)
    block_scripts = arguments.get("block_scripts", True)
    compress_html = arguments.get("compress_html", True)
    extract_content = arguments.get("extract_content", False)
    include_metadata = arguments.get("include_metadata", True)
    max_tokens = min(arguments.get("max_tokens", 20000), 25000)  # Cap at 25000
    truncate_method = arguments.get("truncate_method", "truncate")
    offset = max(arguments.get("offset", 0), 0)  # Ensure non-negative
    limit = arguments.get("limit")

    try:
        # Create temporary file for output
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.html', delete=False) as tmp_file:
            output_path = tmp_file.name

        # Build single-file command
        if output_content:
            # Use dump-content to get HTML directly from stdout
            cmd = ["single-file", url]
            cmd.append("--dump-content")
        else:
            # Save to file
            cmd = ["single-file", url, output_path]
        
        # Add options based on arguments
        if block_images:
            cmd.append("--block-images")
        if block_scripts:
            cmd.append("--block-scripts")
        if compress_html:
            cmd.append("--compress-HTML")
        
        # Add some useful defaults
        cmd.extend([
            "--browser-headless",
            "--browser-wait-until", "networkIdle",
            "--remove-hidden-elements",
            "--remove-unused-styles",
            "--remove-unused-fonts"
        ])

        logger.info(f"Executing: {' '.join(cmd)}")

        # Run single-file command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )

        if result.returncode != 0:
            error_msg = f"single-file failed with return code {result.returncode}"
            if result.stderr:
                error_msg += f": {result.stderr}"
            raise RuntimeError(error_msg)

        # Get content based on method used
        raw_html = ""
        if output_content:
            # Content should be in stdout when using --dump-content
            raw_html = result.stdout
            logger.info(f"Read {len(raw_html)} characters from stdout")
        elif os.path.exists(output_path):
            # Read from file when not using --dump-content
            try:
                with open(output_path, 'r', encoding='utf-8') as f:
                    raw_html = f.read()
                logger.info(f"Read {len(raw_html)} characters from {output_path}")
            except Exception as e:
                logger.error(f"Failed to read output file: {e}")

        # Clean up temporary file if it was created
        if not output_content:
            try:
                os.unlink(output_path)
            except OSError:
                pass

        # Process content based on extraction options
        if output_content and raw_html:
            extracted = extract_content_and_metadata(raw_html, extract_content, include_metadata)
            
            # Prepare response
            response_text = f"Successfully fetched webpage: {url}\n"
            
            if include_metadata and extracted["metadata"]:
                response_text += "\n## Metadata\n"
                meta = extracted["metadata"]
                if meta.get("title"):
                    response_text += f"**Title:** {meta['title']}\n"
                if meta.get("author"):
                    response_text += f"**Author:** {meta['author']}\n"
                if meta.get("date"):
                    response_text += f"**Date:** {meta['date']}\n"
                if meta.get("description"):
                    response_text += f"**Description:** {meta['description']}\n"
                if meta.get("sitename"):
                    response_text += f"**Site:** {meta['sitename']}\n"
                if meta.get("language"):
                    response_text += f"**Language:** {meta['language']}\n"
            
            if extract_content and extracted["content"]:
                content_to_add = extracted["content"]
                
                # Apply pagination first if requested
                pagination_info = None
                if offset > 0 or limit is not None:
                    content_to_add, pagination_info = paginate_content(content_to_add, offset, limit)
                
                # Then apply token truncation
                content_to_add, was_truncated = truncate_content(content_to_add, max_tokens, truncate_method)
                
                # Build response with pagination info
                if pagination_info:
                    response_text += f"\n## Extracted Content (chars {pagination_info['offset']}-{pagination_info['offset'] + pagination_info['returned_chars']} of {pagination_info['total_chars']})\n"
                    if pagination_info['has_more']:
                        response_text += f"*Note: More content available. Use offset={pagination_info['offset'] + pagination_info['returned_chars']} to continue.*\n\n"
                else:
                    response_text += f"\n## Extracted Content\n"
                
                response_text += content_to_add
                
                if was_truncated:
                    logger.info(f"Content was truncated to fit within {max_tokens} tokens")
                    
            elif not extract_content and raw_html:
                content_to_add = raw_html
                
                # Apply pagination first if requested
                pagination_info = None
                if offset > 0 or limit is not None:
                    content_to_add, pagination_info = paginate_content(content_to_add, offset, limit)
                
                # Then apply token truncation
                content_to_add, was_truncated = truncate_content(content_to_add, max_tokens, truncate_method)
                
                # Build response with pagination info
                if pagination_info:
                    response_text += f"\n## HTML Content (chars {pagination_info['offset']}-{pagination_info['offset'] + pagination_info['returned_chars']} of {pagination_info['total_chars']})\n"
                    if pagination_info['has_more']:
                        response_text += f"*Note: More content available. Use offset={pagination_info['offset'] + pagination_info['returned_chars']} to continue.*\n\n"
                else:
                    response_text += f"\n## HTML Content ({len(raw_html)} characters)\n"
                
                response_text += content_to_add
                
                if was_truncated:
                    logger.info(f"HTML content was truncated to fit within {max_tokens} tokens")
        elif output_content and not raw_html:
            response_text = f"Successfully fetched webpage: {url}\nRequested content but no content was returned"
        else:
            response_text = f"Successfully fetched webpage: {url}\nWebpage saved successfully."

        return [
            types.TextContent(
                type="text",
                text=response_text
            )
        ]

    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Timeout while fetching {url}")
    except Exception as e:
        raise RuntimeError(f"Error fetching webpage: {str(e)}")

async def main():
    # Run the server using stdin/stdout streams
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="single-file-mcp",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

def run():
    """Entry point for the package"""
    asyncio.run(main())

if __name__ == "__main__":
    run()