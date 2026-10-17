const nextConfig = {
  // next build must not replace the running next dev asset tree.
  distDir: process.env.NODE_ENV === "development" ? ".next-dev" : ".next-build",
};

export default nextConfig;
