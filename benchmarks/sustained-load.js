import http from "k6/http";
import { check } from "k6";

export const options = {
  scenarios: {
    relay: {
      executor: "constant-arrival-rate",
      rate: Number(__ENV.RATE || 100),
      timeUnit: "1s",
      duration: __ENV.DURATION || "2m",
      preAllocatedVUs: Number(__ENV.PRE_ALLOCATED_VUS || 100),
      maxVUs: Number(__ENV.MAX_VUS || 500),
    },
  },
  thresholds: {
    dropped_iterations: ["count==0"],
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<3000", "p(99)<5000"],
  },
};

const baseUrl = __ENV.BASE_URL || "http://127.0.0.1:8080";
const relayKey = __ENV.RELAY_KEY;

export default function () {
  const response = http.post(
    `${baseUrl}/search`,
    JSON.stringify({ query: "TavilyMux sustained load", search_depth: "basic" }),
    { headers: { Authorization: `Bearer ${relayKey}`, "Content-Type": "application/json" } },
  );
  check(response, { "search completed": (result) => result.status === 200 });
}
