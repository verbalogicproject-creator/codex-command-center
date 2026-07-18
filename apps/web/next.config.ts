import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  output: "export",
  outputFileTracingRoot: path.join(process.cwd(), "../.."),
  images: { unoptimized: true },
  turbopack: {},
};

export default nextConfig;
