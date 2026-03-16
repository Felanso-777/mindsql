[33mcommit 8e374c78165ccf2d8fba9c0a38d621f514afd433[m[33m ([m[1;36mHEAD[m[33m -> [m[1;32mchore/ui-cleanup[m[33m)[m
Author: alvinns <alvin.neelankavil@gmail.com>
Date:   Sat Mar 14 13:40:56 2026 +0530

    updated print banner with switch , connect, set_tokens commands

[33mcommit 03d4b08b648a884b425799f8d8942426cdd1e50b[m[33m ([m[1;31morigin/main[m[33m, [m[1;31morigin/HEAD[m[33m, [m[1;32mmain[m[33m)[m
Merge: 1689930 97ea7d1
Author: Felanso-777 <adamfelanso4@gmail.com>
Date:   Sat Mar 14 00:57:21 2026 +0530

    updated mindsql commands ,added Refresh logic.
    
    Updating mindsql commands and added new feature called Refresh logic which will update database in mindsql dynamically.

[33mcommit 97ea7d1d8d7bed6d8d499ca69c418f02b15e4787[m[33m ([m[1;31morigin/Updating-mindsql-commands[m[33m)[m
Author: alvinns <alvin.neelankavil@gmail.com>
Date:   Sat Mar 14 00:53:47 2026 +0530

    chore: suppress SQLAlchemy warnings for unrecognized data types

[33mcommit 1b1ddc4a229862e10bd41269b73b6101e5580816[m
Author: alvinns <alvin.neelankavil@gmail.com>
Date:   Sat Mar 14 00:38:24 2026 +0530

    feat: implement dynamic schema auto-refresh after ai generated sql commands

[33mcommit 1ef0e478f3787a3ed7de84a7f472d4759f3fb03a[m
Author: alvinns <alvin.neelankavil@gmail.com>
Date:   Sat Mar 14 00:34:10 2026 +0530

    feat: allow global SHOW DATABASES for standard sql execution

[33mcommit 9ba7126abdb39de7720b0f8d8ce1bb882187467d[m
Author: alvinns <alvin.neelankavil@gmail.com>
Date:   Sat Mar 14 00:27:33 2026 +0530

    update mindsql strict  command function

[33mcommit 876a0af6724c1d9bbf39d38b21bb0438a414a615[m
Author: alvinns <alvin.neelankavil@gmail.com>
Date:   Sat Mar 14 00:12:11 2026 +0530

    refactor: simplify chat mode to only explain and output SQL

[33mcommit 16899305612d15b623fecbb58a36dcf35bff0f26[m
Merge: 01a0b2e 86d9d4e
Author: Felanso-777 <adamfelanso4@gmail.com>
Date:   Fri Mar 13 23:42:28 2026 +0530

    connecting to ai and DB picking
    
    user can login with their database credentials ,and they can select their own ai model ,which their system can easily handle.

[33mcommit 86d9d4ef2b15936102a589923b2e63c1407d8d9f[m[33m ([m[1;31morigin/User-login-wizard-and-db-picker[m[33m, [m[1;32mUser-login-wizard-and-db-picker[m[33m)[m
Author: alvinns <alvin.neelankavil@gmail.com>
Date:   Fri Mar 13 23:21:13 2026 +0530

    feat: add direct connect command using cached credentials

[33mcommit ab537cb34cf74e08a9d551e9b5d8d5d5b61d9410[m
Author: alvinns <alvin.neelankavil@gmail.com>
Date:   Fri Mar 13 23:19:05 2026 +0530

    feat: implement interactive server login wizard for connect command

[33mcommit 3677b01cb0b618b85f74777b0b0af54d64ba062a[m
Author: alvinns <alvin.neelankavil@gmail.com>
Date:   Fri Mar 13 23:17:18 2026 +0530

    feat: add interactive switch command for database navigation

[33mcommit 8d4d425abb0d5a951ed63be81c6cd98c92f15a19[m
Author: alvinns <alvin.neelankavil@gmail.com>
Date:   Fri Mar 13 23:12:33 2026 +0530

    feat: add set_tokens command to adjust LLM context window

[33mcommit 5cbfc40a6a77de958cf20edc62ec247dc53cab4f[m
Author: alvinns <alvin.neelankavil@gmail.com>
Date:   Fri Mar 13 23:09:28 2026 +0530

    feat: implement USE command for quick database switching

[33mcommit 5aa157b864ce0567bdd463c692f531764bfd0abe[m
Author: alvinns <alvin.neelankavil@gmail.com>
Date:   Fri Mar 13 23:05:04 2026 +0530

    feat: add dynamic database name to SQL prompt

[33mcommit 01a0b2e2a1b10d3a9c8ec373f073818112f0b244[m
Merge: 339eef6 c988d99
Author: Felanso-777 <adamfelanso4@gmail.com>
Date:   Thu Mar 12 22:50:46 2026 +0530

    added all packages in to requirements.txt
    
    all packages are mentioned

[33mcommit c988d9955edbf6650f20cc7105da4e6c2ec05cea[m[33m ([m[1;31morigin/requirements[m[33m)[m
Author: Felanso-777 <adamfelanso4@gmail.com>
Date:   Thu Mar 12 17:18:26 2026 +0000

    needed packages for runnning

[33mcommit 339eef646ac47cdcacc0c5f7707874907fc058d7[m
Merge: ec31c86 c3da4a7
Author: Felanso-777 <adamfelanso4@gmail.com>
Date:   Thu Mar 12 22:40:55 2026 +0530

    updation of git ignore
    
    git ignore -update

[33mcommit 8129e0236cdaf7af38531b992200e3e9a8e18248[m
Author: alvinns <alvin.neelankavil@gmail.com>
Date:   Sat Mar 7 00:52:51 2026 +0530

    refactor: unify engine check and welcome message logic

[33mcommit 59caaa0559bdc5cd78fc2f22eaf89db1fa44f4cb[m
Author: alvinns <alvin.neelankavil@gmail.com>
Date:   Sat Mar 7 00:48:25 2026 +0530

    feat: restore previous DB session and initialize prompt session
    
    - Restore credentials and engine if saved DB URL exists
    - Load saved schema context from file
    - Initialize PromptSession with history and styling
    - Handle case when no previous DB session exists

[33mcommit b091ccdfb5dd96cdb253c775693cdfda91e93b26[m
Author: alvinns <alvin.neelankavil@gmail.com>
Date:   Sat Mar 7 00:41:00 2026 +0530

    Add session state and credential management for database connections
    
    - Introduced session variables for DB engine, server engine, and schema context
    - Implemented credential caching to allow database switching without re-login
    - Added helper functions to build DB URLs and restore credentials from saved URL

[33mcommit ec31c86fed65bd5eea38818e5f63533339ba0b32[m
Author: Alvin N S <163659881+alvinns@users.noreply.github.com>
Date:   Sat Mar 7 00:25:37 2026 +0530

    feat: introduce first-time configuration and model initialization (#8)
    
    * feat: introduce first-time configuration and model initialization
    
    - Add interactive prompts for model directory and context size (n_ctx)
    - Implement auto-download for Qwen 2.5 Coder with file size validation
    - Add persistent JSON settings to save user preferences
    - Initialize Llama model safely with error handling at startup
    
    * refactor: remove redundant code line
    
    * Update model download source and filename
    
    - Change MODEL_DOWNLOAD_URL to point to Hugging Face repository
    - Update default model filename to qwen2.5-coder-3b-instruct.Q4_K_M.gguf
    
    * refactor: remove redundant code line @app.commands
    
    * feat: implement safety guardrails for DDL and modifying queries
    
    - Add list of forbidden keywords (CREATE, ALTER, DROP, DELETE, etc.)
    - Implement interactive terminal prompt asking for explicit user permission
    - Bypass standard schema validation if the user approves a structural change

[33mcommit 664a1b0ab7255c7363ed0fee04e5880907f55100[m
Merge: 354b5a3 03fb4ba
Author: Felanso-777 <adamfelanso4@gmail.com>
Date:   Fri Mar 6 23:08:23 2026 +0530

    migrating from ollama to llama.cpp
    
    migration to llama and encoding schemes

[33mcommit 03fb4ba3c392eb148d876310c7a78a85e3a2e7d2[m
Author: alvinns <alvin.neelankavil@gmail.com>
Date:   Fri Mar 6 22:56:56 2026 +0530

    migrated ollama to llama cpp, utf-8

[33mcommit c3da4a7c88b1f86e5d1fc90eec8f5b67ee2996a3[m[33m ([m[1;31morigin/git-ignore-updation[m[33m)[m
Author: Felanso-777 <adamfelanso4@gmail.com>
Date:   Fri Mar 6 11:29:57 2026 +0000

    git ignore file is updated .

[33mcommit 26b2c6fcf2ed85418637c5435815454dc9a27c93[m[33m ([m[1;31morigin/initial_setup[m[33m, [m[1;32minitial_setup[m[33m)[m
Author: alvinns <alvin.neelankavil@gmail.com>
Date:   Sat Feb 28 10:53:38 2026 +0530

    Add pathlib import (Path) for file path handling

[33mcommit cd68dfc025fc747fa1485da6eea71c23c38a956f[m
Author: alvinns <alvin.neelankavil@gmail.com>
Date:   Sat Feb 28 00:22:12 2026 +0530

    Add an automated GGUF model downloader using urllib integrated with a rich progress bar. This feature provides users with real-time visual feedback in the terminal during the setup process, displaying the download percentage, transfer speed, and estimated time remaining, while gracefully catching and logging any network errors.

[33mcommit eec8e871e409974a8c08cc5e2d7ffc8eb34aad44[m
Author: alvinns <alvin.neelankavil@gmail.com>
Date:   Sat Feb 28 00:05:18 2026 +0530

    schema,db_config, settings, history ,model url path configuration to home directory

[33mcommit 354b5a339ed4a4e1ae02