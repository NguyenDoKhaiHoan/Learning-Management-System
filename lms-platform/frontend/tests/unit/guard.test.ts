import { expect, it } from "vitest";
import { guardRoute, homeFor } from "../../src/routes/guard";
const user = (roles: string[]) => ({
  id: "1",
  username: "test",
  email: "test@example.test",
  roles,
});

it("requires authentication for direct protected links", () => {
  expect(guardRoute("/courses/1", null)).toBe("login");
  expect(guardRoute("/admin", null)).toBe("login");
  expect(guardRoute("/login", null)).toBe("allow");
});
it("allows only the current role's portal", () => {
  expect(guardRoute("/admin", user(["STUDENT"]))).toBe("forbidden");
  expect(guardRoute("/instructor", user(["STUDENT"]))).toBe("forbidden");
  expect(guardRoute("/student", user(["STUDENT"]))).toBe("allow");
  expect(homeFor(user(["INSTRUCTOR", "ADMIN"]))).toBe("/admin");
  expect(homeFor(user([]))).toBe("/forbidden");
});
it("does not reuse old roles after a new server profile is received", () => {
  expect(guardRoute("/instructor", user(["INSTRUCTOR"]))).toBe("allow");
  expect(guardRoute("/instructor", user(["STUDENT"]))).toBe("forbidden");
});
