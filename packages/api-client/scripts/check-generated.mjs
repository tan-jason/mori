import { execFileSync } from "node:child_process";

const cwd = new URL("../../../", import.meta.url);
const generatedPaths = ["packages/api-client/openapi.json", "packages/api-client/src"];

execFileSync("git", ["diff", "--exit-code", "--", ...generatedPaths], { cwd });
const untracked = execFileSync(
  "git",
  ["ls-files", "--others", "--exclude-standard", "--", ...generatedPaths],
  { cwd, encoding: "utf8" },
);

if (untracked.trim()) {
  throw new Error("Generated API contract differs from committed files. Run the contract generation steps.");
}
