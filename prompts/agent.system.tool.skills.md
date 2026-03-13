### skills_tool

#### overview

skills are folders with instructions scripts files
give agent extra capabilities
agentskills.io standard

#### workflow
1. skill list titles descriptions in system prompt section available skills
2. use skills_tool:load to get full skill instructions and context
4. use code_execution_tool to run scripts or read files

#### examples

##### skills_tool:list

list all skills with metadata name version description tags author
only use when details needed

```xml
<response>
  <thoughts>Need to find skills with certain properties.</thoughts>
  <headline>Listing all available skills</headline>
  <tool_name>skills_tool:list</tool_name>
  <tool_args></tool_args>
</response>
```

##### skills_tool:load

loads complete SKILL.md content instructions procedures
returns metadata content file tree
use when potential skill identified and want usage instructions
use again when no longer in history

```xml
<response>
  <thoughts>User needs PDF form extraction; pdf_editing skill will provide procedures. Loading full skill content.</thoughts>
  <headline>Loading PDF editing skill</headline>
  <tool_name>skills_tool:load</tool_name>
  <tool_args>
    <skill_name>pdf_editing</skill_name>
  </tool_args>
</response>
```

##### executing skill scripts

use skills_tool:load identify skill script files and instructions
use code_execution_tool runtime terminal to execute
write command and parameters as instructed
use full paths or cd to skill directory

```xml
<response>
  <thoughts>Need to convert PDF to images. Skill provides convert_pdf_to_images.py; using code_execution_tool to run it.</thoughts>
  <headline>Converting PDF to images</headline>
  <tool_name>code_execution_tool</tool_name>
  <tool_args>
    <runtime>terminal</runtime>
    <code>python /path/to/skill/scripts/convert_pdf_to_images.py /path/to/document.pdf /tmp/images</code>
  </tool_args>
</response>
```

#### skills guide
use skills when relevant for task
load skill before use
read / execute files with code_execution_tool
follow instructions in skill
mind relative paths
conversation history discards old messages use skills_tool:load again when lost