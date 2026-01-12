I found a limitation. I need that this is suitable to use on multiple repositories.

So, we are going to implement a way to store the configuration that has the capability to addapt to different repos

My first thought is to create a config.ini that has all the current sections, eg paths, ticket_pattern, branches, etc, but when the user adds a hook, we create a new specific sections for this repo (when this sections don't exists).

Then interactively ask the user about this repo specifics, and copy the values in the default section. In the paths, add the repo name so the workspace_base = ./tickets/<repo_name>

To change the config, it is going to be necessary to check first if the user is in one of the known repo. If yes, change this repo config, if no, ask for changing the default config.

As UX command line expert, try to find issues and propose solutions or alternatives.

ask me for every other option, and just plan the steps to do this. 