import { proxyProspecting } from "@/lib/api/prospecting-proxy";
export async function POST(
  request: Request,
  { params }: { params: Promise<{ searchId: string }> },
) {
  return proxyProspecting(request, "cancel", (await params).searchId);
}
