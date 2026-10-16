import { proxyProspecting } from "@/lib/api/prospecting-proxy";
export async function POST(request: Request) {
  return proxyProspecting(request, "start");
}
