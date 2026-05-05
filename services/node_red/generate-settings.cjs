const fs = require("fs");
const path = require("path");

const bcrypt = require(path.join("/usr/src/node-red", "node_modules", "bcryptjs"));
const user = process.env.NODE_RED_ADMIN_USER || "admin";
const pass = process.env.NODE_RED_ADMIN_PASSWORD || "changeme";
const hash = bcrypt.hashSync(pass, 8);
const settings = `module.exports = {
  diagnosticLogging: false,
  logging: { console: { level: "info", metrics: false } },
  httpAdminRoot: "/node-red",
  httpNodeRoot: "/node-red",
  adminAuth: {
    type: "credentials",
    users: [{
      username: ${JSON.stringify(user)},
      password: ${JSON.stringify(hash)},
      permissions: "*"
    }]
  }
};
`;
fs.writeFileSync("/data/settings.js", settings);
