// Test-only (TASK-002 AC-3): the e2e API behind a delay, as a database waking from idle answers.
// Every request waits COLD_API_DELAY_MS, then is forwarded to COLD_API_TARGET unchanged. It lives
// in e2e/ so the app and the API carry no test switch for it.
import http from "node:http";

const port = Number(process.env.COLD_API_PORT);
const target = process.env.COLD_API_TARGET;
const delayMs = Number(process.env.COLD_API_DELAY_MS ?? 3000);

http
  .createServer((req, res) => {
    setTimeout(() => {
      const upstream = http.request(
        new URL(req.url ?? "/", target),
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
    }, delayMs);
  })
  .listen(port, "127.0.0.1");
