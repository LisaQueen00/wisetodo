from mcp.server.mcpserver import MCPServer

server = MCPServer("wisetodo-test")


@server.tool()
def echo(value: str) -> str:
    return value


if __name__ == "__main__":
    server.run()
