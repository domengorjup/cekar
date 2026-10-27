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

### Open Cekar from your phone's home screen

With the Home Assistant Android app you can open Cekar in one tap, which is handy in the shop:

1. In the app, open **Settings → Companion app → Manage shortcuts**.
2. Add a shortcut of type **Dashboard** with the path `/a6b1e57a_cekar` and a label such as "Cekar".
3. Long-press the Home Assistant app icon: the shortcut is in its menu. Drag it onto the home screen to keep it there.

The path is the part after your Home Assistant address when Cekar is open in the sidebar. The `a6b1e57a` prefix comes from the repository URL and stays the same as long as the add-on is installed from `https://github.com/domengorjup/cekar`. See the [companion app docs](https://companion.home-assistant.io/docs/integrations/android-shortcuts/) for details.

## Who you are

In the add-on, Cekar uses your Home Assistant user. The first time you open it, you are added to the list of people automatically. Other household members appear in **Settings** only after they have opened Cekar once themselves.

Standalone, nobody appears by themselves: people are added by hand, either on **Who are you?** or with **Add person** in **Settings**.

If Cekar cannot tell who you are (standalone mode, or a client that does not pass the user), it shows **Who are you?**. Pick your name, or add yourself under **Not in the list?**. Cekar remembers the choice on that device. You can change it later in **Settings > Who are you?**.

## Choose the members

Shopping lists work for everyone from the start. Shared expenses need at least two **members**.

1. Open **Settings**.
2. Under **Shared expenses**, switch on everyone who takes part. Children, guests and tablet accounts can stay off. They can still use the lists.

Until two people are members, the Expenses tab asks you to do this. See [Settings](settings.md).
