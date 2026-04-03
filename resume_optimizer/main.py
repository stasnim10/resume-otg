"""
Resume Optimizer - Desktop Application
Tkinter-based GUI for resume optimization using OpenAI
"""
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from tkinter import ttk
import os
from pathlib import Path

from llm_client import ResumeOptimizerClient
from docx_handler import extract_text_from_docx, optimize_resume


class ResumeOptimizerApp:
    """Main application class"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Resume Optimizer")
        self.root.geometry("900x800")
        
        self.resume_path = None
        self.resume_text = None
        self.llm_client = None
        
        self._setup_ui()
        self._init_llm()
    
    def _setup_ui(self):
        """Setup tkinter UI"""
        # Title
        title = ttk.Label(self.root, text="Resume AI Optimizer", font=("Arial", 16, "bold"))
        title.pack(pady=10)
        
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # === RESUME SECTION ===
        resume_label = ttk.Label(main_frame, text="1. Upload Resume", font=("Arial", 11, "bold"))
        resume_label.pack(anchor="w", pady=(10, 5))
        
        resume_btn_frame = ttk.Frame(main_frame)
        resume_btn_frame.pack(fill="x", pady=5)
        
        self.resume_btn = ttk.Button(
            resume_btn_frame,
            text="Select Resume (.docx)",
            command=self._select_resume
        )
        self.resume_btn.pack(side="left", padx=5)
        
        self.resume_status = ttk.Label(resume_btn_frame, text="No file selected", foreground="red")
        self.resume_status.pack(side="left", padx=5)
        
        # === JOB DESCRIPTION SECTION ===
        jd_label = ttk.Label(main_frame, text="2. Paste Job Description", font=("Arial", 11, "bold"))
        jd_label.pack(anchor="w", pady=(15, 5))
        
        self.jd_text = scrolledtext.ScrolledText(main_frame, height=8, width=100)
        self.jd_text.pack(fill="both", expand=True, pady=5)
        self.jd_text.insert("1.0", "Paste job description here...")
        
        # === CONTROL BUTTONS ===
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=15)
        
        self.optimize_btn = ttk.Button(
            btn_frame,
            text="🚀 Optimize Resume",
            command=self._optimize,
            state="disabled"
        )
        self.optimize_btn.pack(side="left", padx=5)
        
        reset_btn = ttk.Button(btn_frame, text="Reset", command=self._reset)
        reset_btn.pack(side="left", padx=5)
        
        # === OUTPUT SECTION ===
        output_label = ttk.Label(main_frame, text="Status & Output", font=("Arial", 11, "bold"))
        output_label.pack(anchor="w", pady=(15, 5))
        
        self.output_text = scrolledtext.ScrolledText(main_frame, height=10, width=100)
        self.output_text.pack(fill="both", expand=True, pady=5)
        self.output_text.config(state="disabled")
    
    def _init_llm(self):
        """Initialize LLM client"""
        try:
            self.llm_client = ResumeOptimizerClient()
            self._log("✅ OpenAI API initialized\n")
        except ValueError as e:
            self._log(f"❌ {str(e)}\n", "error")
            messagebox.showerror("API Error", str(e))
    
    def _select_resume(self):
        """File dialog for resume selection"""
        file_path = filedialog.askopenfilename(
            title="Select Resume",
            filetypes=[("Word Documents", "*.docx"), ("All Files", "*.*")]
        )
        
        if file_path:
            try:
                self.resume_path = file_path
                self.resume_text = extract_text_from_docx(file_path)
                
                filename = Path(file_path).name
                self.resume_status.config(text=f"✅ {filename}", foreground="green")
                self._log(f"✅ Resume loaded: {filename}\n")
                
                # Enable optimize button if JD is also provided
                self._check_ready()
                
            except Exception as e:
                self._log(f"❌ Error loading resume: {str(e)}\n", "error")
                messagebox.showerror("Error", f"Failed to load resume: {str(e)}")
    
    def _check_ready(self):
        """Check if both resume and JD are ready"""
        jd_text = self.jd_text.get("1.0", "end").strip()
        has_resume = self.resume_path is not None
        has_jd = jd_text and jd_text != "Paste job description here..."
        
        if has_resume and has_jd and self.llm_client:
            self.optimize_btn.config(state="normal")
        else:
            self.optimize_btn.config(state="disabled")
    
    def _optimize(self):
        """Main optimization workflow"""
        if not self.resume_path or not self.resume_text:
            messagebox.showerror("Error", "Please select a resume")
            return
        
        jd_text = self.jd_text.get("1.0", "end").strip()
        if not jd_text or jd_text == "Paste job description here...":
            messagebox.showerror("Error", "Please paste a job description")
            return
        
        self._log("🔄 Starting optimization...\n")
        self.optimize_btn.config(state="disabled")
        
        try:
            # Step 1: Call LLM
            self._log("📤 Sending to OpenAI...\n")
            success, parsed_json, raw_response = self.llm_client.optimize_resume(
                self.resume_text,
                jd_text
            )
            
            if not success:
                self._log(f"❌ {parsed_json}\n", "error")
                messagebox.showerror("API Error", parsed_json)
                self.optimize_btn.config(state="normal")
                return
            
            # Step 2: Format replacements
            self._log("📦 Processing recommendations...\n")
            replacements = self.llm_client.format_replacements(parsed_json)
            
            if not replacements:
                self._log("⚠️ No replacements generated\n", "warning")
                messagebox.showwarning("No Changes", "No optimization recommendations were found")
                self.optimize_btn.config(state="normal")
                return
            
            self._log(f"Found {len(replacements)} optimization(s):\n")
            for r in replacements:
                anchor_preview = r["match_anchor"][:60]
                self._log(f"  • {anchor_preview}...\n")
            
            # Step 3: Apply to document
            self._log("\n📝 Applying changes to document...\n")
            output_path = self._generate_output_filename(self.resume_path)
            success_msg, message = optimize_resume(
                self.resume_path,
                replacements,
                output_path
            )
            
            if success_msg:
                self._log(f"\n{message}\n", "success")
                self._log(f"💾 Saved to: {output_path}\n", "success")
                messagebox.showinfo("Success", f"Resume optimized!\n\nSaved as:\n{output_path}")
            else:
                self._log(f"\n❌ {message}\n", "error")
                messagebox.showerror("Error", message)
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._log(f"\n❌ {error_msg}\n", "error")
            messagebox.showerror("Error", error_msg)
        
        finally:
            self.optimize_btn.config(state="normal")
    
    def _generate_output_filename(self, original_path: str) -> str:
        """Generate output filename with _Optimized suffix"""
        path = Path(original_path)
        output_name = f"{path.stem}_Optimized{path.suffix}"
        output_path = path.parent / output_name
        return str(output_path)
    
    def _log(self, message: str, level: str = "info"):
        """Write to output text area"""
        self.output_text.config(state="normal")
        self.output_text.insert("end", message)
        self.output_text.see("end")
        self.output_text.config(state="disabled")
    
    def _reset(self):
        """Reset the application"""
        self.resume_path = None
        self.resume_text = None
        self.resume_status.config(text="No file selected", foreground="red")
        self.jd_text.delete("1.0", "end")
        self.jd_text.insert("1.0", "Paste job description here...")
        self.output_text.config(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.config(state="disabled")
        self.optimize_btn.config(state="disabled")
        self._log("✨ Application reset\n")


def main():
    root = tk.Tk()
    app = ResumeOptimizerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
