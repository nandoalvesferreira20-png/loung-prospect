import { NextRequest,NextResponse } from "next/server";
import {serverAuth} from "@/lib/auth/server";
export async function GET(request:NextRequest){
  const token_hash=request.nextUrl.searchParams.get("token_hash");
  const type=request.nextUrl.searchParams.get("type");
  if(token_hash&&(type==="invite"||type==="recovery")){
    const auth=await serverAuth();const {error}=await auth.auth.verifyOtp({token_hash,type});
    if(!error)return NextResponse.redirect(new URL("/atualizar-senha",request.url));
  }
  return NextResponse.redirect(new URL("/login?invalid_link=1",request.url));
}
