"""
Resume Optimizer - Local Desktop Application
Tkinter-based GUI for deterministic resume optimization
"""
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from tkinter import ttk
from pathlib import Path

from json_parser import parse_replacement_payload
from docx_handler import extract_text, apply_replacements, apply_cover_letter_replacements, save_cover_letter_content


class ResumeOptimizerApp:
    """Main tkinter application"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Resume Optimizer")
        self.root.geometry("1000x1400")
        
        self.resume_path = None
        self.resume_text = None
        self.cover_letter_path = None
        self.cover_letter_text = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup tkinter UI with two distinct phases"""
        # Title
        title = ttk.Label(self.root, text="Resume Optimizer", font=("Arial", 16, "bold"))
        title.pack(pady=5)
        
        subtitle = ttk.Label(self.root, text="Local, offline, no API", font=("Arial", 10))
        subtitle.pack(pady=2)
        
        # Main frame with scrollable content
        main_frame = ttk.Frame(self.root, padding="5")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # ============================================
        # PHASE 1: RESUME OPTIMIZATION
        # ============================================
        phase1_label = ttk.Label(main_frame, text="PHASE 1: Resume Optimization", font=("Arial", 13, "bold"), foreground="blue")
        phase1_label.pack(anchor="w", pady=(10, 10))
        
        phase1_box = ttk.LabelFrame(main_frame, text="Resume Optimizer", padding="8")
        phase1_box.pack(fill="x", pady=8)
        
        # Step 1: Resume Upload
        step1_label = ttk.Label(phase1_box, text="Step 1: Upload Resume (.docx)", font=("Arial", 11, "bold"))
        step1_label.pack(anchor="w", pady=(0, 5))
        
        resume_btn_frame = ttk.Frame(phase1_box)
        resume_btn_frame.pack(fill="x", pady=5)
        
        self.resume_btn = ttk.Button(
            resume_btn_frame,
            text="📁 Select Resume",
            command=self._select_resume
        )
        self.resume_btn.pack(side="left", padx=5)
        
        self.resume_status = ttk.Label(resume_btn_frame, text="No file selected", foreground="red")
        self.resume_status.pack(side="left", padx=10)
        
        # Step 2: JSON Payload
        step2_label = ttk.Label(phase1_box, text="Step 2: Paste JSON Replacement Payload", font=("Arial", 11, "bold"))
        step2_label.pack(anchor="w", pady=(15, 5))
        
        # Help text
        help_text = ttk.Label(
            phase1_box,
            text="⚠️ IMPORTANT: match_anchor must be the FULL paragraph text (copy entire paragraph/bullet from the document)",
            font=("Arial", 9),
            foreground="red"
        )
        help_text.pack(anchor="w", pady=(0, 5))
        
        self.json_text = scrolledtext.ScrolledText(phase1_box, height=6, width=120)
        self.json_text.pack(fill="both", pady=5)
        self.json_text.insert("1.0", self._example_json())
        
        # Optimize Button
        self.optimize_btn = ttk.Button(
            phase1_box,
            text="🚀 Optimize Resume",
            command=self._optimize,
            state="disabled"
        )
        self.optimize_btn.pack(pady=10)
        
        # ============================================
        # PHASE 2: COVER LETTER UPDATE
        # ============================================
        phase2_label = ttk.Label(main_frame, text="PHASE 2: Cover Letter Update", font=("Arial", 13, "bold"), foreground="green")
        phase2_label.pack(anchor="w", pady=(20, 10))
        
        phase2_box = ttk.LabelFrame(main_frame, text="Cover Letter Content Manager", padding="8")
        phase2_box.pack(fill="x", pady=8)
        
        # Step 1: Cover Letter Upload
        step1_cl = ttk.Label(phase2_box, text="Step 1: Upload Cover Letter Template (.docx)", font=("Arial", 11, "bold"))
        step1_cl.pack(anchor="w", pady=(0, 5))
        
        cover_btn_frame = ttk.Frame(phase2_box)
        cover_btn_frame.pack(fill="x", pady=5)
        
        self.cover_btn = ttk.Button(
            cover_btn_frame,
            text="📁 Select Cover Letter",
            command=self._select_cover_letter
        )
        self.cover_btn.pack(side="left", padx=5)
        
        self.cover_status = ttk.Label(cover_btn_frame, text="No file selected", foreground="red")
        self.cover_status.pack(side="left", padx=10)
        
        # Step 2: Cover Letter Content
        step2_cl = ttk.Label(phase2_box, text="Step 2: Paste New Cover Letter Content", font=("Arial", 11, "bold"))
        step2_cl.pack(anchor="w", pady=(15, 5))
        
        helper_note_cover = ttk.Label(
            phase2_box,
            text="Paste your ChatGPT-generated cover letter text. Click 'Update Cover Letter' to replace the body while preserving formatting.",
            font=("Arial", 9),
            foreground="gray"
        )
        helper_note_cover.pack(anchor="w", pady=(0, 5))
        
        self.cover_content_text = scrolledtext.ScrolledText(phase2_box, height=5, width=120)
        self.cover_content_text.pack(fill="both", pady=5)
        self.cover_content_text.insert("1.0", "Paste your ChatGPT-generated cover letter text here...")
        
        # Update Button
        save_btn_frame = ttk.Frame(phase2_box)
        save_btn_frame.pack(fill="x", pady=15)
        
        self.save_cover_btn = ttk.Button(
            save_btn_frame,
            text="✉️ Update Cover Letter",
            command=self._save_cover_letter_content,
            state="disabled"
        )
        self.save_cover_btn.pack(fill="x", padx=5, ipady=10)
        
        # ============================================
        # UTILITIES
        # ============================================
        utilities_frame = ttk.Frame(main_frame)
        utilities_frame.pack(fill="x", pady=15)
        
        reset_btn = ttk.Button(utilities_frame, text="🔄 Clear All", command=self._reset)
        reset_btn.pack(side="left", padx=5)
        
        # ============================================
        # OUTPUT
        # ============================================
        output_label = ttk.Label(main_frame, text="Status & Output", font=("Arial", 11, "bold"))
        output_label.pack(anchor="w", pady=(15, 5))
        
        self.output_text = scrolledtext.ScrolledText(main_frame, height=3, width=120)
        self.output_text.config(state="disabled")
        
        self._log("✨ Ready to optimize\n")
    
    def _example_json(self) -> str:
        """Return example JSON"""
        return """{
  "summary_replacement": {
    "match_anchor": "MBA candidate and strategy-driven operations professional with experience supporting revenue, growth, and go-to-market execution through analytics, systems, and cross-functional leadership. Proven track record of driving performance through KPI reporting, process optimization, enablement programs, and scalable operating models across consulting, technology, healthcare, and global retail environments. Strong analytical foundation with hands-on experience in Excel, SQL, Tableau, SAP, and CRM-enabled workflows, partnering closely with sales, marketing, finance, product, and leadership teams to improve visibility, efficiency, and decision-making.",
    "replacement_text": "MBA candidate (Class of 2026) with 6+ years of international supply chain and logistics leadership, managing $50M–$240M global operations across distribution, transportation, and supplier networks. Proven track record of delivering multi-million-dollar cost savings, leading cross-functional transformations, and building data-driven operating models across retail, consulting, and healthcare environments."
  },
  "bullet_replacements": [
    {
      "match_anchor": "Built a go-to-market supply and pricing model by evaluating international suppliers, cost structures, and margin scenarios, enabling a successful product launch with a 60% gross margin",
      "replacement_text": "Developed a supplier sourcing and margin optimization model by analyzing international cost structures and pricing scenarios, enabling product launch at 60% gross margin"
    },
    {
      "match_anchor": "Managed an 8,000+ container network across 15 international warehouses within a $240M operation, applied route optimization software, and led a 35-person cross-functional team to reduce freight costs by $400K annually",
      "replacement_text": "Managed an 8,000+ container global transportation network within a $240M operation, leading a 35-person cross-functional team and deploying network optimization strategies to reduce annual spend by $400K"
    }
  ],
  "skills_replacements": [
    {
      "match_anchor": "Supply Chain & Operations: Supply Chain Management, Operations Management, Cloud Experience, Supply Chain Analytics",
      "replacement_text": "Supply Chain & Operations: Supply Chain Management, Operations Management, Network Optimization, Capacity Planning, Supplier Performance Management, Lean Process Improvement, Logistics Cost Optimization, KPI Governance"
    },
    {
      "match_anchor": "Analytics: Excel, SQL, Tableau",
      "replacement_text": "Analytics & Data Tools: Advanced Excel (Financial Modeling, Scenario Analysis), SQL, Tableau, Data Visualization, KPI Dashboard Development"
    },
    {
      "match_anchor": "Programming & Systems: Python, R, SAP",
      "replacement_text": "ERP & Enterprise Systems: SAP (Reporting & Data Extraction), CRM-Enabled Workflow Support, Programming & Technical Tools: Python, R"
    },
    {
      "match_anchor": "Web & Mobile Application: GitHub, Cursor, Google Firebase Studio, Figma, IOS app Developer, Xcode, Android app developer",
      "replacement_text": "Digital Product & Systems Exposure: GitHub, Firebase Studio, Figma, Xcode, Android Development Tools"
    }
  ]
}
"""
    
    def _select_resume(self):
        """File dialog for resume"""
        file_path = filedialog.askopenfilename(
            title="Select Resume",
            filetypes=[("Word Documents", "*.docx"), ("All Files", "*.*")]
        )
        
        if file_path:
            try:
                self.resume_path = file_path
                self.resume_text = extract_text(file_path)
                
                filename = Path(file_path).name
                self.resume_status.config(text=f"✅ {filename}", foreground="green")
                self._log(f"✅ Loaded: {filename}\n")
                
                self._check_ready()
                
            except Exception as e:
                self._log(f"❌ Error loading resume: {str(e)}\n")
                messagebox.showerror("Error", f"Failed to load resume: {str(e)}")

    def _select_cover_letter(self):
        """File dialog for cover letter"""
        file_path = filedialog.askopenfilename(
            title="Select Cover Letter",
            filetypes=[("Word Documents", "*.docx"), ("All Files", "*.*")]
        )

        if file_path:
            try:
                self.cover_letter_path = file_path
                self.cover_letter_text = extract_text(file_path)

                filename = Path(file_path).name
                self.cover_status.config(text=f"✅ {filename}", foreground="green")
                self._log(f"✅ Loaded cover letter: {filename}\n")

                self._check_ready()

            except Exception as e:
                self._log(f"❌ Error loading cover letter: {str(e)}\n")
                messagebox.showerror("Error", f"Failed to load cover letter: {str(e)}")
    
    def _check_ready(self):
        """Check if ready to optimize"""
        json_text = self.json_text.get("1.0", "end").strip()
        has_resume = self.resume_path is not None
        has_cover_letter = self.cover_letter_path is not None
        has_json = json_text and json_text != self._example_json()
        
        if has_resume and has_json:
            self.optimize_btn.config(state="normal")
        else:
            self.optimize_btn.config(state="disabled")

        # Enable cover letter save button when template is loaded
        if has_cover_letter:
            self.save_cover_btn.config(state="normal")
        else:
            self.save_cover_btn.config(state="disabled")
    
    def _optimize(self):
        """Main optimization workflow — runs I/O in a background thread."""
        if not self.resume_path:
            messagebox.showerror("Error", "Please select a resume")
            return

        json_text = self.json_text.get("1.0", "end").strip()
        if not json_text:
            messagebox.showerror("Error", "Please paste JSON payload")
            return

        self._log("🔄 Starting optimization...\n")
        self.optimize_btn.config(state="disabled")

        def _worker():
            try:
                self._log("📋 Parsing JSON...\n")
                payload = parse_replacement_payload(json_text)
                self._log("✅ JSON valid\n")

                self._log("📝 Applying replacements...\n")
                success, message = apply_replacements(self.resume_path, payload)

                if success:
                    self._log(f"\n{message}\n")
                    self.root.after(0, lambda: messagebox.showinfo("Success", message))
                else:
                    self._log(f"\n{message}\n")
                    self.root.after(0, lambda: messagebox.showerror("Error", message))

            except ValueError as e:
                msg = str(e)
                self._log(f"\n❌ {msg}\n")
                self.root.after(0, lambda: messagebox.showerror("Error", msg))

            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                self._log(f"\n❌ {error_msg}\n")
                self.root.after(0, lambda: messagebox.showerror("Error", error_msg))

            finally:
                self.root.after(0, lambda: self.optimize_btn.config(state="normal"))

        threading.Thread(target=_worker, daemon=True).start()
    
    def _save_cover_letter_content(self):
        """Update cover letter — runs I/O in a background thread."""
        if not self.cover_letter_path:
            messagebox.showerror("Error", "Please select a cover letter template first")
            return

        content = self.cover_content_text.get("1.0", "end").strip()

        if not content or content == "Paste your ChatGPT-generated cover letter text here...":
            messagebox.showerror("Error", "Please paste cover letter content first")
            return

        # Save to a new _Updated file to preserve the original template
        _p = Path(self.cover_letter_path)
        output_path = str(_p.parent / f"{_p.stem}_Updated{_p.suffix}")

        self._log("✉️ Updating cover letter...\n")
        self.save_cover_btn.config(state="disabled")

        template_path = self.cover_letter_path

        def _worker():
            try:
                success, message = save_cover_letter_content(template_path, content, output_path)

                if success:
                    self._log(f"\n{message}\n")
                    self.root.after(0, lambda: messagebox.showinfo("Success", message))
                    self.root.after(0, self._clear_cover_letter_input)
                else:
                    self._log(f"\n{message}\n")
                    self.root.after(0, lambda: messagebox.showerror("Error", message))

            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                self._log(f"\n❌ {error_msg}\n")
                self.root.after(0, lambda: messagebox.showerror("Error", error_msg))

            finally:
                self.root.after(0, lambda: self.save_cover_btn.config(state="normal"))

        threading.Thread(target=_worker, daemon=True).start()

    def _clear_cover_letter_input(self):
        """Reset the cover letter content text area to its placeholder."""
        self.cover_content_text.delete("1.0", "end")
        self.cover_content_text.insert("1.0", "Paste your ChatGPT-generated cover letter text here...")
    
    def _log(self, message: str):
        """Write to output"""
        self.output_text.config(state="normal")
        self.output_text.insert("end", message)
        self.output_text.see("end")
        self.output_text.config(state="disabled")
    
    def _reset(self):
        """Reset app"""
        self.resume_path = None
        self.resume_text = None
        self.resume_status.config(text="No file selected", foreground="red")
        self.cover_letter_path = None
        self.cover_letter_text = None
        self.cover_status.config(text="No file selected", foreground="red")
        self.cover_content_text.delete("1.0", "end")
        self.cover_content_text.insert("1.0", "Paste your ChatGPT-generated cover letter text here...")
        self.json_text.delete("1.0", "end")
        self.json_text.insert("1.0", self._example_json())
        self.output_text.config(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.config(state="disabled")
        self.optimize_btn.config(state="disabled")
        self.save_cover_btn.config(state="disabled")
        self._log("✨ Application reset\n")


def main():
    root = tk.Tk()
    app = ResumeOptimizerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
