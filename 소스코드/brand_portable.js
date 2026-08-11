const rcedit = require("rcedit");

const [exePath, iconPath] = process.argv.slice(2);
if (!exePath || !iconPath) {
  throw new Error("Usage: node brand_portable.js <portable.exe> <app.ico>");
}

rcedit(exePath, {
  "version-string": {
    CompanyName: "Serotonin",
    FileDescription: "Serotonin 바로캡처 Portable",
    ProductName: "Serotonin 바로캡처",
    LegalCopyright: "Copyright © 2026 이은호",
  },
  "file-version": "1.0.0.0",
  "product-version": "1.0.0.0",
  icon: iconPath,
  "requested-execution-level": "asInvoker",
}).catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
