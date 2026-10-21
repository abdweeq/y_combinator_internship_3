'use strict';

// Run from this repository with: node analyze.cjs
// Uses the SQLite module included with Node.js 24; no npm install is needed.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { DatabaseSync } = require('node:sqlite');

const root = __dirname;
const databasePath = path.join(root, 'shiptivity.db');
if (!fs.existsSync(databasePath)) {
  throw new Error('Place analyze.cjs and answer.sql beside the repository file shiptivity.db.');
}

const sql = fs.readFileSync(path.join(root, 'answer.sql'), 'utf8');
const parts = sql.split(/^-- QUERY: ([a-z0-9_]+)\s*$/m);
const db = new DatabaseSync(databasePath, { readOnly: true });
const queries = {};

try {
  for (let index = 1; index < parts.length; index += 2) {
    queries[parts[index]] = db.prepare(parts[index + 1]).all();
  }
} finally {
  db.close();
}

const results = {
  source: 'https://github.com/insidesherpa/-shiptivitas-3',
  database_sha256: crypto.createHash('sha256')
    .update(fs.readFileSync(databasePath)).digest('hex'),
  release_date_utc: '2018-06-02',
  timezone: 'UTC',
  metric_definition: 'Distinct users with at least one recorded login per UTC day.',
  queries,
};

const output = path.join(root, 'analysis-results.json');
fs.writeFileSync(output, JSON.stringify(results, null, 2) + '\n');

console.log('SQL queries completed. Results: ' + output);
console.table(queries.matched_28_day_comparison);
console.table(queries.card_activity_summary);
console.log('Daily rows: ' + queries.daily_active_users.length);
console.log('Card rows: ' + queries.status_changes_by_card.length);
