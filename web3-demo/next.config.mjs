const nextConfig = {
  // Keep local dev/build assets separate; Vercel expects the standard .next output.
  distDir: process.env.VERCEL === "1"
    ? ".next"
    : process.env.NODE_ENV === "development" ? ".next-dev" : ".next-build",
};

export default nextConfig;
