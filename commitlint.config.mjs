export default {
  extends: ["@commitlint/config-conventional"],
  rules: {
    // Dependabot's auto-generated changelog bodies frequently include
    // long URLs (release notes, compare links) that exceed the default
    // 100-char limit. Lift to 200 so those land cleanly while still
    // catching unwrapped prose in human commits.
    "body-max-line-length": [2, "always", 200],
  },
};
