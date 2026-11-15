import { redirect } from "next/navigation";

// The Pass now lives inside the tier system.
export default function Pass() {
  redirect("/tiers");
}
