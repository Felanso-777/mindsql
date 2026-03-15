# MindSQL

A privacy-focused, AI-powered SQL assistant that runs entirely on your local machine. Helps beginners learn SQL and assists developers with databases without external data transmission.

## Table of Contents
- Overview
- Why MindSQL
- Features
- Prerequisites
- Installation
- Usage
- Team
- License

## Overview

MindSQL is a command-line tool combining local AI models with SQL databases. Offers strict SQL generation, conversational interaction, and ASCII data visualization. Runs completely offline for maximum privacy.

## Why MindSQL

Addresses cloud AI security risks by:
- Running locally with no internet after setup
- Using Qwen 2.5 Coder 3B model via llama.cpp
- Zero data transmission to third parties
- Supporting SQL learning and confidential data work

## Features

**Core Capabilities**
- Natural language to SQL generation
- Interactive query validation/execution
- Schema-aware auto-completion
- ASCII bar charts
- Multi-database switching
- Transaction support with rollback
- Conversational SQL guidance

**Privacy & Security**
- Fully offline operation
- Local AI execution
- Secure credential storage

**User Experience**
- Rich terminal UI with syntax highlighting
- Context-aware completion
- Command history
- Configurable AI memory
- Schema validation

## Prerequisites

**System Requirements**
- OS: Windows/macOS/Linux
- Python 3.11
- RAM: 4GB min (8GB recommended)
- Storage: 3GB+ free
- MySQL database

**Required Software**
- Python 3.11 + pip
- MySQL Server
- Git

## Installation

1. **Clone repo**
git clone https://github.com/Felanso-777/mindsql.git
cd mindsql

text

2. **Install dependencies**
pip install -r requirements.txt

text

3. **First run** (`python main_ac.py`)
- Sets model path (~/.mindsql/models)
- Downloads Qwen 2.5 Coder 3B (2.3GB)
- Our fine tuned model: https://huggingface.co/AKHILDEVCV/MindSQL-Model-GGUF
- Configures memory: Low/Medium/High/Max/Custom

4. **Connect database**
SQL (no db)> connect

text

## Usage

**Database Commands**
- `connect` - Login wizard
- `use <db>` - Switch database
- `switch` - Database selector
- `exit`/`quit` - Exit

**AI Commands**
- `mindsql <query>` - NL to SQL
- `mindsql_ans <question>` - Explanations
- `mindsql_plot <request>` - ASCII charts

**Config**
- `set_tokens <number>` - Adjust AI memory

**SQL Support**: Full DDL/DML/DCL/TCL

**Examples**:
SQL> mindsql show users from last month
SELECT * FROM users WHERE registration_date >= DATE_SUB(NOW(), INTERVAL 1 MONTH);

SQL> mindsql_plot sales by category

text

## Configuration

**Model**: `~/.mindsql/models/` or edit `~/.mindsql/settings.json`
**Schema cache**: `~/.mindsql/schema.txt`

## Team

- Adam Felanso Sijo
- Akhildev C Vasudevan
- Alex Chittilappilly
- Alvin N S

Educational project exploring privacy-focused AI database tools.

## License

For educational/development use. Comply with dependency licenses (Qwen 2.5, llama.cpp).

## Troubleshooting

**Model issues**: Check internet/space, manual download from HuggingFace (https://huggingface.co/AKHILDEVCV/MindSQL-Model-GGUF)
**Connection**: Verify MySQL running/credentials/permissions
**Performance**: Reduce tokens, close heavy apps
**AI timeout**: Simplify queries, lower token count