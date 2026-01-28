# Hyperlink Harvester

A demonstration of using Generative AI to create precise, specification-driven prompts that GitHub Copilot can execute to generate production-quality Python code.

## Overview

This project showcases a two-step AI workflow:
1. **Prompt Engineering with ChatGPT** – Generate a detailed, spec-driven prompt for a coding task
2. **Code Generation with GitHub Copilot** – Execute that prompt to produce working Python code

## Workflow

### Step 1: Initial Prompt (ChatGPT)

I started by asking ChatGPT to help craft a precise prompt:

`I want to create a prompt for GitHub Copilot to help me write a prompt to scavange a web site (https://docs.molt.bot/) and harvest the links on the page and save the hyperlinks to a file called "links.txt". Help me write the prompt that is precise and spec driven`

### Step 2: Refinement (ChatGPT)

I then refined the requirements with a follow-up:

`I mainly want the links from the navigation pane on the left and I want to remove duplicate`

### Step 3: Code Generation (GitHub Copilot)

1. Saved the ChatGPT-generated prompt as `ChatGPTPrompts.md` in VS Code
2. Opened the file and used GitHub Copilot Agent mode with the command: **"execute the prompt in the open file"**
3. Copilot generated a complete, production-ready Python CLI tool

## Result

The generated `extract_links.py` script:
- Extracts only sidebar navigation links from documentation sites
- Removes duplicates while preserving order
- Normalizes URLs (strips fragments, ensures HTTPS)
- Provides CLI options for customization (`--start-url`, `--out`, `--verbose`)
- The result links can be imported into Google's NotebookLM to do grounded research based on trusted (vetted) knowledge sources.
