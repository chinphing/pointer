## "Multimodal (Vision) Agent Tools" available:

### vision_load:
load image data to LLM
use paths arg for attachments
multiple images if needed
only bitmaps supported convert first if needed

**Example usage**:
```xml
<response>
  <thoughts>I need to see the image...</thoughts>
  <headline>Loading image for visual analysis</headline>
  <tool_name>vision_load</tool_name>
  <tool_args>
    <paths>/path/to/image.png</paths>
  </tool_args>
</response>
```
