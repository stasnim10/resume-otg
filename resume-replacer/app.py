import streamlit as st
import json
import tempfile
from replacer import replace_bullets
from utils import parse_before_after_format

st.title("Resume Bullet Replacer")

uploaded_file = st.file_uploader("Upload Resume (.docx)", type=["docx"])

# Add instructions
with st.expander("📋 How to Format Your Replacements", expanded=False):
    st.markdown("""
    **Option 1: JSON Format**
    ```json
    [
      {
        "original": "Led global $50M project overseeing people",
        "revised": "Directed $50M supply chain operations program"
      },
      {
        "original": "Managed team of 10 engineers",
        "revised": "Led cross-functional engineering team of 10+"
      }
    ]
    ```
    
    **Option 2: BEFORE/AFTER Format**
    ```
    BEFORE:
    Led global $50M project overseeing people
    
    AFTER:
    Directed $50M supply chain operations program
    
    BEFORE:
    Managed team of 10 engineers
    
    AFTER:
    Led cross-functional engineering team of 10+
    ```
    """)

input_format = st.radio("Select Input Format:", ["JSON", "BEFORE/AFTER"], horizontal=True)

if input_format == "JSON":
    user_input = st.text_area("Paste Replacement JSON", height=200, placeholder='[{"original": "...", "revised": "..."}]')
else:
    user_input = st.text_area("Paste BEFORE/AFTER Text", height=200, placeholder="BEFORE:\nYour original text\n\nAFTER:\nYour revised text")

if uploaded_file and user_input:
    try:
        # Parse input based on format
        if input_format == "JSON":
            replacements = json.loads(user_input)
        else:
            replacements = parse_before_after_format(user_input)
        
        # Validate replacements
        if not replacements:
            st.error("No replacements found. Please check your input format.")
        elif not all("original" in r and "revised" in r for r in replacements):
            st.error("Invalid format. Each replacement must have 'original' and 'revised' keys.")
        else:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                tmp.write(uploaded_file.read())
                temp_path = tmp.name

            output_path = replace_bullets(temp_path, replacements)

            with open(output_path, "rb") as f:
                st.download_button(
                    label="📥 Download Optimized Resume",
                    data=f,
                    file_name="optimized_resume.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

            st.success(f"✅ Successfully processed {len(replacements)} replacement(s)!")

    except json.JSONDecodeError as e:
        st.error(f"❌ JSON Error: {e}\n\nPlease check your JSON format or switch to BEFORE/AFTER format.")
    except Exception as e:
        st.error(f"❌ Error: {e}")
