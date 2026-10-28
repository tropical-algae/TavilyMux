import http from "k6/http";
import { check } from "k6";

export const options = {
  scenarios: {
    sustained: {
      executor: "constant-vus",
      vus: Number(__ENV.VUS || 50),
      duration: __ENV.DURATION || "30s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<3000"],
  },
};

const baseUrl = __ENV.BASE_URL || "http://127.0.0.1:8080";
const relayKey = __ENV.RELAY_KEY;

export default function () {
  const response = http.post(
    `${baseUrl}/search`,
    JSON.stringify({ query: "TavilyMux load verification", search_depth: "basic" }),
    { headers: { Authorization: `Bearer ${relayKey}`, "Content-Type": "application/json" } },
  );
  check(response, { "search completed": (result) => result.status === 200 });
}
