/**
 * Starts the task bot within a minute of Igor emailing it.
 *
 * GitHub fires this repo's scheduled workflows only 5 or 6 times a day, so the task bot
 * (task_bot.py, workflow task-bot.yml) is started from here instead. This script runs every
 * minute on Google's servers, inside Igor's own Google account, and does two cheap checks:
 *
 *   1. Is there a task email the bot has not taken yet? (a message his account sent to his
 *      +claude address without the "Claude tasks" label)        -> start the workflow now.
 *   2. Are drafts from an earlier task still waiting to be sent? -> start it every 15 minutes,
 *      so the task log flips to "Done" soon after he sends them.
 *
 * It sends GitHub nothing but "run the workflow": no email content ever leaves Gmail here.
 *
 * Setup (once, about five minutes) is in bots/TASK_BOT.md. In short: paste this file into a new
 * project at script.google.com, add the "Gmail API" service, store a GitHub token as the script
 * property GITHUB_TOKEN, then run `install` once.
 */

var REPO = 'igormscaldini/growth-advisor-clearerthinking';
var WORKFLOW = 'task-bot.yml';
var TAG = 'claude';                       // tasks go to <address>+claude@gmail.com
var TAKEN_SEARCH = 'label:claude-tasks';  // Gmail's search form of the label "Claude tasks"
var DRAFTS_SEARCH = 'label:claude-tasks-drafts-waiting';
var RETRY_MINUTES = 15;                   // start again if the same email is still untaken
var DRAFTS_MINUTES = 15;

function taskAddress() {
  return Session.getEffectiveUser().getEmail().toLowerCase().replace('@', '+' + TAG + '@');
}

/** The newest message matching a Gmail search, or null. Uses the Gmail API (message level). */
function newestMessageId(query) {
  var res = Gmail.Users.Messages.list('me', { q: query, maxResults: 1 });
  return res.messages && res.messages.length ? res.messages[0].id : null;
}

/** Ask GitHub to run the workflow. Returns true when GitHub accepted it. */
function startWorkflow() {
  var token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('Script property GITHUB_TOKEN is missing (see bots/TASK_BOT.md).');
  var res = UrlFetchApp.fetch(
    'https://api.github.com/repos/' + REPO + '/actions/workflows/' + WORKFLOW + '/dispatches', {
      method: 'post',
      contentType: 'application/json',
      headers: {
        Authorization: 'Bearer ' + token,
        Accept: 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28'
      },
      payload: JSON.stringify({ ref: 'main' }),
      muteHttpExceptions: true
    });
  if (res.getResponseCode() !== 204) {
    console.error('GitHub answered ' + res.getResponseCode() + ': ' + res.getContentText().slice(0, 300));
    return false;
  }
  return true;
}

/** The function the every-minute trigger runs. */
function checkClaudeTasks() {
  var props = PropertiesService.getScriptProperties();
  var now = Date.now();
  var lastStart = Number(props.getProperty('lastStart') || 0);
  var minutesSince = (now - lastStart) / 60000;

  var pending = newestMessageId('in:sent to:' + taskAddress() + ' -' + TAKEN_SEARCH + ' newer_than:7d');
  if (pending) {
    // The bot labels a task as its first step, a minute or two after the start. Until then the
    // same email is still "pending": do not start a second run for it unless it stays that way.
    if (pending === props.getProperty('lastPending') && minutesSince < RETRY_MINUTES) return;
    if (startWorkflow()) {
      props.setProperty('lastPending', pending);
      props.setProperty('lastStart', String(now));
    }
    return;
  }

  if (minutesSince >= DRAFTS_MINUTES && newestMessageId(DRAFTS_SEARCH)) {
    if (startWorkflow()) props.setProperty('lastStart', String(now));
  }
}

/** Run once by hand: (re)creates the every-minute trigger and does a first check. */
function install() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'checkClaudeTasks') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('checkClaudeTasks').timeBased().everyMinutes(1).create();
  checkClaudeTasks();
  console.log('Installed. Tasks go to ' + taskAddress());
}

/** Run by hand to check the GitHub token: starts one workflow run (it finds nothing to do). */
function testStart() {
  console.log(startWorkflow() ? 'GitHub accepted the start.' : 'GitHub refused: see the error above.');
}

/** Run by hand to stop the bot being started from here (the slow GitHub schedule remains). */
function uninstall() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'checkClaudeTasks') ScriptApp.deleteTrigger(t);
  });
}
