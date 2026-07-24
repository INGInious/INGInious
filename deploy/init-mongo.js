let password =  process.env.INGINIOUS_SUPERADMIN_PASSWORD;
if (password == undefined) {
  throw "INGINIOUS_SUPERADMIN_PASSWORD env variable is not set.";
}
password = 'argon2id-' + password;

let username = process.env.INGINIOUS_SUPERADMIN_USERNAME;
username = username != undefined ? username : "superadmin";

let realname = process.env.INGINIOUS_SUPERADMIN_REALNAME;
realname = realname != undefined ? realname : "INGInious superadmin";

let email = process.env.INGINIOUS_SUPERADMIN_EMAIL;
email = email != undefined ? email : "superadmin@inginious.org";

let lang = process.env.INGINIOUS_SUPERADMIN_LANG;
lang = lang != undefined ? lang : "en";

let indent = process.env.INGINIOUS_SUPERADMIN_INDENT;
indent = indent != undefined ? indent : "4";

db.users.insertOne({
  "username": username,
  "realname": realname,
  "email": email,
  "password": password,
  "bindings": {},
  "language": lang,
  "code_indentation": indent
});
