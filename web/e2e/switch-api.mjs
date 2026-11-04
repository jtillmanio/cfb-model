// Test-only (TASK-054 AC-3, AC-6): the e2e API behind a switch, so a journey can stop the API and
// start it again without stopping uvicorn, and count the server-side calls a page makes.
//   POST /__e2e/down  every API request after this has its connection dropped, as a stopped API
//   POST /__e2e/up    requests are forwarded to SWITCH_API_TARGET again
//   GET  /__e2e/count {"count": n}, the number of /api/py/* requests forwarded so far
// It lives in e2e/ so the app and the API carry no test switch for it (as cold-api.mjs).
import http from "node:http";

const port = Number(process.env.SWITCH_API_PORT);
const target = process.env.SWITCH_API_TARGET;

let down = false;
let count = 0;

function control(req, res) {
  const send = (status, body) => {
    res.writeHead(status, { "content-type": "application/json" });
    res.end(JSON.stringify(body));
  };
  if (req.method === "POST" && req.url === "/__e2e/down") {
    down = true;
    return send(200, { down });
  }
  if (req.method === "POST" && req.url === "/__e2e/up") {
    down = false;
    return send(200, { down });
  }
  if (req.method === "GET" && req.url === "/__e2e/count") return send(200, { count });
  return send(404, { error: "unknown control" });
}

http
  .createServer((req, res) => {
    const url = req.url ?? "/";
    if (url.startsWith("/__e2e/")) return control(req, res);
    // Stopped: no answer at all, so the web server's fetch fails as it does against a dead port.
    if (down) return req.socket.destroy();
    if (url.startsWith("/api/py/")) count += 1;
    const upstream = http.request(
      new URL(url, target),
      { method: req.method, headers: req.headers },
      (answer) => {
        res.writeHead(answer.statusCode ?? 502, answer.headers);
        answer.pipe(res);
      },
    );
    upstream.on("error", () => {
      res.writeHead(502);
      res.end();
    });
    req.pipe(upstream);
  })
  .listen(port, "127.0.0.1");
