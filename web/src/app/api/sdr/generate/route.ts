import { proxySdr } from "@/lib/api/sdr-proxy";
export const runtime = "nodejs";
export const maxDuration = 45;
export async function POST(request: Request) { return proxySdr(request, "generate"); }
