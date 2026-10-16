import { proxyProspecting } from "@/lib/api/prospecting-proxy";
export async function GET(
  request: Request,
  { params }: { params: Promise<{ searchId: string }> },
) {
  return proxyProspecting(request, "status", (await params).searchId);
}
