import { notFound } from "next/navigation";
import LegacyLab from "./LegacyLab";

export default function LabPage() {
  if (process.env.NODE_ENV !== "development") notFound();
  return <LegacyLab />;
}
