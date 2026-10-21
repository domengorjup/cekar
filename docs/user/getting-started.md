# Getting started

## Install the add-on

You need Home Assistant OS or Supervised, with Supervisor 2026.10.3 or later.

!!! note "Add-ons are called apps in newer Home Assistant"
    Since Home Assistant 2026.6, add-ons are called **apps**: **Settings > Apps > Install app** replaces **Settings > Add-ons > Add-on store**. The steps are the same.

1. Open **Settings > Add-ons > Add-on store**, open the menu (three dots) and choose **Repositories**.
2. Paste `https://github.com/domengorjup/cekar` and click **Add**.
3. Find **Cekar** in the store and click **Install**. The image is built on your Home Assistant host, so the first install takes a few minutes.
4. Click **Start**, then turn on **Show in sidebar**.

To run it outside Home Assistant, see the README.

## Open it

Click **Cekar** in the Home Assistant sidebar. Every Home Assistant user can open it, not only administrators. There is no separate login.

## Who you are

In the add-on, Cekar uses your Home Assistant user. The first time you open it, you are added to the list of people automatically.

If Cekar cannot tell who you are (standalone mode, or a client that does not pass the user), it shows **Who are you?**. Pick your name, or add yourself under **Not in the list?**. Cekar remembers the choice on that device. You can change it later in **Settings > Who are you?**.

## Choose the members

Shopping lists work for everyone from the start. Shared expenses need at least two **members**.

1. Open **Settings**.
2. Under **Shared expenses**, switch on everyone who takes part. Children, guests and tablet accounts can stay off. They can still use the lists.

Until two people are members, the Expenses tab asks you to do this. See [Settings](settings.md).
