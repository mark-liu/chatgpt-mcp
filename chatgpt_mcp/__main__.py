from mcp.server.fastmcp import FastMCP
from chatgpt_mcp.mcp_tools import setup_mcp_tools

mcp = FastMCP("chatgpt")
setup_mcp_tools(mcp)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
