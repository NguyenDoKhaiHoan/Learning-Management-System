import type { CurrentUser } from "../../../shared/contracts/api";

export function homeFor(user: CurrentUser): string {
  if (user.roles.includes("ADMIN")) return "/admin";
  if (user.roles.includes("INSTRUCTOR")) return "/instructor";
  if (user.roles.includes("STUDENT")) return "/student";
  return "/forbidden";
}

export function guardRoute(
  path: string,
  user: CurrentUser | null,
): "allow" | "login" | "forbidden" {
  if (path === "/login") return "allow";
  if (!user) return "login";
  const role = (
    {
      "/admin": "ADMIN",
      "/instructor": "INSTRUCTOR",
      "/student": "STUDENT",
    } as Record<string, string>
  )[path];
  return role && !user.roles.includes(role) ? "forbidden" : "allow";
}
