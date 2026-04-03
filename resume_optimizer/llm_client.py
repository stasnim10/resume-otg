"""
OpenAI API client for resume optimization
"""
import os
import json
import re
from typing import Tuple, Dict, Any
from openai import OpenAI


class ResumeOptimizerClient:
    """Client for calling OpenAI API with resume optimization prompt"""
    
    def __init__(self, api_key: str = None):
        """
        Initialize OpenAI client.
        
        Args:
            api_key: OpenAI API key. If None, uses OPENAI_API_KEY env var.
        """
        if api_key is None:
            api_key = os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            raise ValueError(
                "❌ OpenAI API key not found. Set OPENAI_API_KEY environment variable."
            )
        
        self.client = OpenAI(api_key=api_key)
        self.prompt_template = self._load_prompt_template()
    
    def _load_prompt_template(self) -> str:
        """Load prompt template from file"""
        try:
            current_dir = os.path.dirname(__file__)
            prompt_path = os.path.join(current_dir, "prompt_template.txt")
            with open(prompt_path, "r") as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError("❌ prompt_template.txt not found in project directory")
    
    def optimize_resume(self, resume_text: str, job_description: str) -> Tuple[bool, Dict[str, Any], str]:
        """
        Send resume + JD to OpenAI and get optimization recommendations.
        
        Args:
            resume_text: Extracted resume text
            job_description: Job description text or pasted content
            
        Returns:
            Tuple of (success: bool, parsed_json: dict, raw_response: str)
        """
        # Format prompt
        prompt = self.prompt_template.format(
            resume_text=resume_text,
            job_description=job_description
        )
        
        # Call OpenAI
        try:
            print("🤖 Calling OpenAI API...")
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7
            )
            
            raw_response = response.choices[0].message.content
            print("✅ Received response from OpenAI")
            
            # Extract JSON from response
            parsed_json = self._extract_json(raw_response)
            return True, parsed_json, raw_response
            
        except Exception as e:
            error_msg = f"OpenAI API Error: {str(e)}"
            return False, {}, error_msg
    
    def _extract_json(self, response_text: str) -> Dict[str, Any]:
        """
        Extract JSON block from response text.
        Uses regex to find the last JSON object in the response.
        
        Args:
            response_text: Raw response from OpenAI
            
        Returns:
            Parsed JSON as dictionary
            
        Raises:
            ValueError: If JSON not found or invalid
        """
        # Search for JSON block (last one in response)
        match = re.search(r'\{[\s\S]*\}\s*$', response_text)
        
        if not match:
            raise ValueError("❌ No JSON block found in response. Check prompt format.")
        
        json_str = match.group(0)
        
        try:
            parsed = json.loads(json_str)
            print("✅ JSON validation successful")
            return parsed
        except json.JSONDecodeError as e:
            raise ValueError(f"❌ Invalid JSON in response: {str(e)}")
    
    def format_replacements(self, parsed_json: Dict[str, Any]) -> list:
        """
        Convert parsed JSON into replacement format for docx_handler.
        
        Args:
            parsed_json: Parsed JSON from LLM response
            
        Returns:
            List of replacement dicts with keys: match_anchor, replacement_text
        """
        replacements = []
        
        # Summary replacement
        if "summary" in parsed_json and parsed_json["summary"]:
            summary = parsed_json["summary"]
            if "original" in summary and "replacement" in summary:
                replacements.append({
                    "match_anchor": summary["original"],
                    "replacement_text": summary["replacement"]
                })
        
        # Bullet points replacements
        if "bullets" in parsed_json and isinstance(parsed_json["bullets"], list):
            for bullet in parsed_json["bullets"]:
                if "original" in bullet and "replacement" in bullet:
                    replacements.append({
                        "match_anchor": bullet["original"],
                        "replacement_text": bullet["replacement"]
                    })
        
        # Technical skills replacement
        if "technical_skills" in parsed_json and parsed_json["technical_skills"]:
            skills = parsed_json["technical_skills"]
            if "original" in skills and "replacement" in skills:
                replacements.append({
                    "match_anchor": skills["original"],
                    "replacement_text": skills["replacement"]
                })
        
        print(f"📦 Formatted {len(replacements)} replacement(s)")
        return replacements
