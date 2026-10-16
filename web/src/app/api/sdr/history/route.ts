import { proxySdr } from "@/lib/api/sdr-proxy";
export const runtime = "nodejs";
export async function POST(request: Request) { return proxySdr(request, "save"); }
