import { notFound } from "next/navigation";
import LegacyDeploy from "./LegacyDeploy";

export default function DeployPage() {
  if (process.env.NODE_ENV !== "development") notFound();
  return <LegacyDeploy />;
}
