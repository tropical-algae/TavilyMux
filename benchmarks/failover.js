import http from "k6/http";
import { check } from "k6";

export const options = {
  vus: Number(__ENV.VUS || 10),
  iterations: Number(__ENV.ITERATIONS || 100),
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<5000"],
  },
};

const baseUrl = __ENV.BASE_URL || "http://127.0.0.1:8080";
const relayKey = __ENV.RELAY_KEY;

export default function () {
  const response = http.post(
    `${baseUrl}/search`,
    JSON.stringify({ query: "TavilyMux failover verification" }),
    { headers: { Authorization: `Bearer ${relayKey}`, "Content-Type": "application/json" } },
  );
  check(response, {
    "request succeeded after routing": (result) => result.status === 200,
    "request id returned": (result) => Boolean(result.headers["X-Tavily-Mux-Request-ID"]),
  });
}
