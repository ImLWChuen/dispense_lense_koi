/**
 * Root Index Page
 *
 * Automatically routes inbound visitors to the primary executive dashboard view (`/dashboard`).
 */

import { redirect } from "next/navigation";

export default function Home() {
    redirect("/dashboard");
}