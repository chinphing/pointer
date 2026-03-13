### notify_user:
This tool can be used to notify the user of a message independent of the current task.

!!! This is a universal notification tool
!!! Supported notification types: info, success, warning, error, progress

#### Arguments:
 *  "message" (string) : The message to be displayed to the user.
 *  "title" (Optional, string) : The title of the notification.
 *  "detail" (Optional, string) : The detail of the notification. May contain html tags.
 *  "type" (Optional, string) : The type of the notification. Can be "info", "success", "warning", "error", "progress".

#### Usage examples:
##### 1: Success notification
```xml
<response>
  <thoughts>Notifying user of task completion.</thoughts>
  <headline>Task completed</headline>
  <tool_name>notify_user</tool_name>
  <tool_args>
    <message>Important notification: task xyz is completed successfully</message>
    <title>Task Completed</title>
    <detail>This is a test notification detail with &lt;a href='https://www.google.com'&gt;link&lt;/a&gt;</detail>
    <type>success</type>
  </tool_args>
</response>
```
##### 2: Error notification
```xml
<response>
  <thoughts>Notifying user of task failure.</thoughts>
  <headline>Task failed</headline>
  <tool_name>notify_user</tool_name>
  <tool_args>
    <message>Important notification: task xyz has failed</message>
    <title>Task Failed</title>
    <detail>This is a test notification detail with link and image.</detail>
    <type>error</type>
  </tool_args>
</response>
```
