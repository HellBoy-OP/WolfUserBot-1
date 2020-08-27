# Copyright (C) 2019 The Raphielscape Company LLC.
#
# Licensed under the Raphielscape Public License, Version 1.d (the "License");
# you may not use this file except in compliance with the License.
# credits to @AvinashReddy3108
#
"""
This module updates the wolfuserbot based on upstream revision
"""

from os import remove, execle, path, environ
import asyncio
import sys

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError, NoSuchPathError

from wolfuserbot import (BOTLOG, BOTLOG_CHATID, CMD_HELP, HEROKU_API_KEY, HEROKU_APP_NAME, UPSTREAM_REPO_URL, UPSTREAM_REPO_BRANCH, TERM_ALIAS)
from wolfuserbot.events import register

requirements_path = path.join(
    path.dirname(path.dirname(path.dirname(__file__))), 'requirements.txt')


async def gen_chlog(repo, diff):
    ch_log = ''
    d_form = "%d/%m/%y"
    for c in repo.iter_commits(diff):
        ch_log += f'•[{c.committed_datetime.strftime(d_form)}]: {c.summary} <{c.author}>\n'
    return ch_log


async def update_requirements():
    reqs = str(requirements_path)
    try:
        process = await asyncio.create_subprocess_shell(
            ' '.join([sys.executable, "-m", "pip", "install", "-r", reqs]),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        await process.communicate()
        return process.returncode
    except Exception as e:
        return repr(e)


async def deploy(event, repo, ups_rem, ac_br, txt):
    if HEROKU_API_KEY is not None:
        import heroku3
        heroku = heroku3.from_key(HEROKU_API_KEY)
        heroku_app = None
        heroku_applications = heroku.apps()
        if HEROKU_APP_NAME is None:
            await event.edit(
                '`[HEROKU]: Please set up the` **HEROKU_APP_NAME** `variable'
                ' to be able to deploy newest changes of wolfuserbot.`'
            )
            repo.__del__()
            return
        for app in heroku_applications:
            if app.name == HEROKU_APP_NAME:
                heroku_app = app
                break
        if heroku_app is None:
            await event.edit(
                f'{txt}\n`Invalid Heroku credentials for deploying wolfuserbot dyno.`'
            )
            return repo.__del__()
        await event.edit('`[HEROKU]:'
                         '\nWolfUserbot dyno build in progress, please wait it can take 7-8 mins`'
                         )
        ups_rem.fetch(ac_br)
        repo.git.reset("--hard", "FETCH_HEAD")
        heroku_git_url = heroku_app.git_url.replace(
            "https://", "https://api:" + HEROKU_API_KEY + "@")
        if "heroku" in repo.remotes:
            remote = repo.remote("heroku")
            remote.set_url(heroku_git_url)
        else:
            remote = repo.create_remote("heroku", heroku_git_url)
        try:
            remote.push(refspec="HEAD:refs/heads/master", force=True)
        except GitCommandError as error:
            await event.edit(f'{txt}\n`Here is the error log:\n{error}`')
            return repo.__del__()
        await event.edit('`Successfully Updated!\n'
                         'Restarting, please wait...`')

        if BOTLOG:
            await event.client.send_message(
                BOTLOG_CHATID, "#UPDATE \n"
                "oub-remix was successfully updated")

    else:
        await event.edit('`[HEROKU]:'
                         '\nPlease set up` **HEROKU_API_KEY** `variable.`'
                         )
    return


async def update(event, repo, ups_rem, ac_br):
    try:
        ups_rem.pull(ac_br)
    except GitCommandError:
        repo.git.reset("--hard", "FETCH_HEAD")
    await update_requirements()
    await event.edit('`Successfully Updated!\n'
                     'WolfBot is restarting... Wait for a second!`')

    if BOTLOG:
            await event.client.send_message(
                BOTLOG_CHATID, "#UPDATE \n"
                "Wolf User Bot was successfully updated")

    # Spin a new instance of bot
    args = [sys.executable, "-m", "wolfuserbot"]
    execle(sys.executable, *args, environ)
    return


@register(outgoing=True, pattern=r"^.update(?: |$)(now|deploy)?")
async def upstream(event):
    "For .update command, check if the bot is up to date, update if specified"
    await event.edit("`Checking for updates, please wait....`")
    conf = event.pattern_match.group(1)
    off_repo = UPSTREAM_REPO_URL
    force_update = False
    try:
        txt = "`Oops.. Updater cannot continue due to "
        txt += "some problems occured`\n\n**LOGTRACE:**\n"
        repo = Repo()
    except NoSuchPathError as error:
        await event.edit(f'{txt}\n`directory {error} is not found`')
        return repo.__del__()
    except GitCommandError as error:
        await event.edit(f'{txt}\n`Early failure! {error}`')
        return repo.__del__()
    except InvalidGitRepositoryError as error:
        if conf is None:
            return await event.edit(
                f"`Unfortunately, the directory {error} does not seem to be a git repository."
                "\nBut we can fix that by force updating the wolfuserbot using .update now.`"
            )
        repo = Repo.init()
        origin = repo.create_remote('upstream', off_repo)
        origin.fetch()
        force_update = True
        repo.create_head('master', origin.refs.master)
        repo.heads.master.set_tracking_branch(origin.refs.master)
        repo.heads.master.checkout(True)

    ac_br = repo.active_branch.name
    if ac_br != UPSTREAM_REPO_BRANCH:
        await event.edit(
            '**[UPDATER]:**\n'
            f'`Looks like you are using your own custom branch ({ac_br}). '
            'in that case, Updater is unable to identify '
            'which branch is to be merged. '
            'please checkout to any official branch`')
        return repo.__del__()
    try:
        repo.create_remote('upstream', off_repo)
    except BaseException:
        pass

    ups_rem = repo.remote('upstream')
    ups_rem.fetch(ac_br)

    changelog = await gen_chlog(repo, f'HEAD..upstream/{ac_br}')

    if changelog == '' and force_update is False:
        await event.edit(
            f'\n`{TERM_ALIAS} is` **updated-af🤘🤘**\n`BRANCH:`**{UPSTREAM_REPO_BRANCH}**\n')
        return repo.__del__()

    if conf is None and force_update is False:
        changelog_str = f'**New UPDATE available for [{ac_br}]:\n\nCHANGELOG:**\n`{changelog}`'
        if len(changelog_str) > 4096:
            await event.edit("`Changelog is too big, view the file to see it.`")
            file = open("output.txt", "w+")
            file.write(changelog_str)
            file.close()
            await event.client.send_file(
                event.chat_id,
                "output.txt",
                reply_to=event.id,
            )
            remove("output.txt")
        else:
            await event.edit(changelog_str)
        return await event.respond('`do ".update now/deploy" to update`')

    if force_update:
        await event.edit(
            '`Force-Syncing to latest stable wolfuserbot code, please wait...`')
    else:
        await event.edit('`Updating Wolf User Bot, please wait....`')
    if conf == "now":
        await update(event, repo, ups_rem, ac_br)
    elif conf == "deploy":
        await deploy(event, repo, ups_rem, ac_br, txt)
    return


CMD_HELP.update({
    'update':
    ".update"
    "\nUsage: Checks if the main wolfuserbot repository has any updates and shows a changelog if so."
    "\n\n.update now"
    "\nUsage: Update your wolfuserbot, if there are any updates in your wolfuserbot repository."
    "\n\n.update deploy"
    "\nUsage: Deploy your wolfuserbot at heroku, if there are any updates in your wolfuserbot repository."
})