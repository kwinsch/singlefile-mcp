# Single-File MCP Server

A powerful Model Context Protocol (MCP) server that provides intelligent web content extraction using [single-file](https://github.com/gildas-lormeau/SingleFile) and [trafilatura](https://github.com/adbar/trafilatura). Perfect for AI agents that need to access and analyze web content from JavaScript-heavy sites.

**GitHub Repository**: [https://github.com/kwinsch/singlefile-mcp](https://github.com/kwinsch/singlefile-mcp)

## Features

### 🌐 Universal Web Content Access
- **JavaScript Support**: Handles modern SPA/React/Vue apps that require browser rendering
- **Clean Content Extraction**: Uses Mozilla's Readability algorithm via trafilatura
- **Rich Metadata**: Extracts title, author, date, description, and more
- **Multiple Output Formats**: Raw HTML or clean markdown-like content

### 📄 Smart Pagination & Token Management
- **Flexible Pagination**: Offset/limit system like file reading tools
- **Token Limits**: Configurable max tokens (up to 25,000)
- **Smart Truncation**: Summary mode shows beginning + end, truncate mode cuts cleanly
- **Navigation Hints**: Clear guidance on how to continue reading large documents

### ⚡ Performance & Control
- **Selective Loading**: Block images/scripts for faster processing
- **Content Compression**: Optional HTML compression
- **Timeout Protection**: Configurable timeouts prevent hanging
- **Error Handling**: Graceful degradation when extraction fails

## Installation

### Prerequisites
- Python 3.8+
- [single-file CLI](https://github.com/gildas-lormeau/SingleFile) - Web page capture tool
- Node.js 16+ (for single-file)
- A supported browser (Chromium, Chrome, Edge, Firefox, etc.)

### Install single-file CLI

The [single-file CLI](https://github.com/gildas-lormeau/SingleFile/tree/master/cli) is essential for this MCP server to work. It uses a real browser engine to accurately capture JavaScript-rendered content.

```bash
npm install -g single-file-cli
```

## Usage with Claude Code

### Quick Install (from PyPI)
```bash
claude mcp add singlefile-mcp -s user -- uvx singlefile-mcp
```

This will automatically install and run the package from PyPI, similar to how Brave Search works!

### Development Install (from local directory)
```bash
claude mcp add singlefile-mcp -s user -- uvx --from /path/to/single-file_mcp singlefile-mcp
```

### Remove old server (if upgrading)
```bash
claude mcp remove single-file-fetcher --scope user
```

### Optional: Add Brave Search MCP
```bash
claude mcp add brave-search -s user -- env BRAVE_API_KEY=YOUR_KEY npx -y @modelcontextprotocol/server-brave-search
```

## API Reference

### fetch_webpage

Fetch and process web content with intelligent extraction.

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | string | *required* | URL of the webpage to fetch |
| `output_content` | boolean | `true` | Whether to return content in response |
| `extract_content` | boolean | `false` | Extract clean text content (recommended) |
| `include_metadata` | boolean | `true` | Include page metadata (title, author, etc.) |
| `block_images` | boolean | `false` | Block image downloads for faster processing |
| `block_scripts` | boolean | `true` | Block JavaScript execution |
| `compress_html` | boolean | `true` | Compress HTML output |
| `max_tokens` | number | `20000` | Maximum tokens in response (max: 25000) |
| `truncate_method` | string | `"truncate"` | How to handle large content: `"truncate"` or `"summary"` |
| `offset` | number | `0` | Character offset to start reading from |
| `limit` | number | `null` | Maximum characters to return |

#### Examples

**Basic content extraction:**
```python
fetch_webpage(
    url="https://example.com/article",
    extract_content=True,
    include_metadata=True
)
```

**Paginated reading of large documents:**
```python
# Get overview
fetch_webpage(
    url="https://docs.example.com/guide",
    extract_content=True,
    limit=5000
)

# Continue reading from offset
fetch_webpage(
    url="https://docs.example.com/guide", 
    extract_content=True,
    offset=5000,
    limit=5000
)
```

**Raw HTML for complex parsing:**
```python
fetch_webpage(
    url="https://app.example.com/dashboard",
    extract_content=False,
    block_scripts=False,
    max_tokens=15000
)
```

## Practical Example: Research Workflow

Here's a real-world example combining Brave Search and Single-File MCP:

**Step 1: Search for information**
```python
# Using Brave Search MCP
brave_web_search(
    query="artificial intelligence history timeline",
    count=5
)
```

**Step 2: Fetch and analyze Wikipedia article**
```python
# Using Single-File MCP to extract content
fetch_webpage(
    url="https://en.wikipedia.org/wiki/History_of_artificial_intelligence",
    extract_content=True,
    include_metadata=True,
    limit=5000  # Get first 5000 chars
)
```

**Result:**
```
Successfully fetched webpage: https://en.wikipedia.org/wiki/History_of_artificial_intelligence

## Metadata
**Title:** History of artificial intelligence - Wikipedia
**Description:** The history of artificial intelligence (AI) began in antiquity...
**Site:** wikipedia.org

## Extracted Content (chars 0-5000 of 45000)
*Note: More content available. Use offset=5000 to continue.*

# History of artificial intelligence

The history of artificial intelligence (AI) began in antiquity, with myths, 
stories and rumors of artificial beings endowed with intelligence...

[Clean, readable article content follows...]
```

**Step 3: Continue reading with pagination**
```python
# Get next section
fetch_webpage(
    url="https://en.wikipedia.org/wiki/History_of_artificial_intelligence",
    extract_content=True,
    offset=5000,
    limit=5000
)
```

This workflow enables AI agents to:
1. Search for current information beyond their training data
2. Extract clean, structured content from any webpage
3. Process JavaScript-heavy sites that other tools can't handle
4. Paginate through long documents intelligently

## Output Format

### With Content Extraction
```
Successfully fetched webpage: https://example.com

## Metadata
**Title:** Example Article
**Author:** John Doe
**Date:** 2024-01-15
**Description:** An informative article about...
**Site:** example.com

## Extracted Content (chars 0-5000 of 12000)
*Note: More content available. Use offset=5000 to continue.*

# Article Title

This is the clean, readable content extracted from the webpage...
```

### Pagination Info
When using offset/limit, responses include:
- Current position: `chars 1000-6000 of 12000`
- Navigation hint: `Use offset=6000 to continue`
- Total size information

## Use Cases

### 📚 Documentation Analysis
Perfect for reading large technical docs, API references, and guides that span multiple pages.

### 📰 News & Article Processing  
Extract clean article content from news sites, blogs, and publications for analysis.

### 🔍 Research & Data Gathering
Gather structured data from websites, including metadata and clean text content.

### 🤖 AI Agent Integration
Enable AI agents to browse and understand web content, even from JavaScript-heavy applications.

### ⚖️ Legal Document Processing
Handle complex legal documents and government sites that require JavaScript rendering.

## Technical Details

### Content Extraction Pipeline
1. **single-file**: Renders JavaScript and saves complete webpage
2. **trafilatura**: Extracts main content using Mozilla Readability algorithm  
3. **Pagination**: Applies offset/limit for manageable chunks
4. **Token Management**: Ensures responses fit within LLM context limits

### Browser Engine
Uses a browser via [single-file](https://github.com/gildas-lormeau/SingleFile) for full JavaScript support:
- Works with any supported browser installed on your system
- Waits for network idle before capture
- Removes hidden elements and unused styles
- Handles dynamic content loading

### Metadata Extraction
Automatically extracts:
- Page title and description
- Author and publication date
- Site name and language
- Categories and tags (when available)

## Error Handling

- **Network Issues**: Graceful timeout with informative errors
- **JavaScript Errors**: Continues processing even if some scripts fail
- **Large Content**: Automatic truncation with clear indicators
- **Invalid URLs**: Clear validation error messages

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/kwinsch/singlefile-mcp.git
cd singlefile-mcp
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install in development mode:
```bash
pip install -e .
```

4. Test locally with Claude Code:
```bash
claude mcp add singlefile-mcp -s user -- uvx --from . singlefile-mcp
```

## License

MIT License - see LICENSE file for details.

## Dependencies

- **[single-file](https://github.com/gildas-lormeau/SingleFile)** - Core web page capture tool that handles JavaScript rendering
- **[trafilatura](https://github.com/adbar/trafilatura)** - Content extraction using Mozilla's Readability algorithm
- **[mcp](https://modelcontextprotocol.io/)** - Model Context Protocol for AI integration

## Acknowledgments

- [single-file by Gildas Lormeau](https://github.com/gildas-lormeau/SingleFile) - Excellent web page capture tool
- [trafilatura](https://github.com/adbar/trafilatura) - Robust content extraction library
- [Model Context Protocol](https://modelcontextprotocol.io/) - Standardized AI integration protocol