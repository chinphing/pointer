### document_query
read and analyze remote/local documents get text content or answer questions
pass a single url/path or a list for multiple documents in "document"
for web documents use "http://" or "https://"" prefix
for local files "file://" prefix is optional but full path is required
if "queries" is empty tool returns document content
if "queries" is a list of strings tool returns answers
supports various formats HTML PDF Office Text etc
usage:

1 get content
```xml
<response>
  <thoughts>I need to read...</thoughts>
  <headline>Reading document</headline>
  <tool_name>document_query</tool_name>
  <tool_args>
    <document>https://.../document</document>
  </tool_args>
</response>
```

2 query document
```xml
<response>
  <thoughts>I need to answer...</thoughts>
  <headline>Querying document</headline>
  <tool_name>document_query</tool_name>
  <tool_args>
    <document>https://.../document</document>
    <queries>What is...
Who is...</queries>
  </tool_args>
</response>
```

3 query multiple documents
```xml
<response>
  <thoughts>I need to compare...</thoughts>
  <headline>Comparing documents</headline>
  <tool_name>document_query</tool_name>
  <tool_args>
    <document>https://.../document-one
file:///path/to/document-two</document>
    <queries>Compare the main conclusions...
What are the key differences...</queries>
  </tool_args>
</response>
```
