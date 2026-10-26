import { serveStdio } from "@modelcontextprotocol/server/stdio";
import { createServer } from "./tools.js";

await serveStdio(() => createServer(), { legacy: "serve" });
