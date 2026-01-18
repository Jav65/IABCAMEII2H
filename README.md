# 🆘 I Am Beyond Cooked and My Exam is in 2 Hours!

> Born out of countless all‑nighters and the chaos of last‑minute studying, this tool provides a single, focused entry point that instantly spins your material into three productivity modes — a cheatsheet (in LaTeX!), flashcards, or a Keynote‑style presentation — letting you dive straight into learning accompanied by AllNighters Agents!

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com)
[![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?style=for-the-badge&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![Vite](https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev)
[![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)
[![LaTeX](https://img.shields.io/badge/LaTeX-008080?style=for-the-badge&logo=latex&logoColor=white)](https://www.latex-project.org/)
[![Atlas RAG](https://img.shields.io/badge/Atlas_RAG-FF6B6B?style=for-the-badge&logo=database&logoColor=white)](https://pypi.org/project/atlas-rag/)

---

## 💡 Inspiration

Born out of countless all‑nighters and the chaos of last‑minute studying, this project tackles a simple pain: **when time is short, decision‑making is the enemy.** "What format should I study in? Where do I even start?"

So, this tool provides a single, focused entry point that instantly spins your material into three productivity modes — a cheatsheet, flashcards, or a Keynote‑style presentation — letting you dive straight into learning instead of planning.

**The goal:** help you prepare for an exam in **two hours or less** with tools that balance speed, clarity, and minimal cognitive friction. You can still edit details where needed without breaking the rest of your workflow — no domino effect of formatting disasters.

---

## ✨ What It Does

### 🏠 Home Page
A clean, centered interface welcomes your input with the ability to upload:
- 📄 PDF documents
- 🖼️ Images (.jpg, .jpeg)
- 📝 Text files (.txt)

From there, pick your mode — **cheatsheet**, **flashcards**, or **presentation** — and jump straight in.

### 📝 Cheatsheet Page
A full **LaTeX editor** with:
- ⚡ Real‑time compile and PDF preview
- 💬 Integrated chat panel for quick, interactive fine‑tuning
- 🔄 Instant synchronization between source and rendered output

Write, render, iterate — all without leaving the page.

### 🎴 Flashcard Page
A JSON editor and deck loader featuring:
- 🔄 Intuitive flip‑card study mode
- 📊 Difficulty-based organization
- 🎯 Interactive learning experience

Type a concept, flip for the answer, and repeat until panic transforms into calm mastery.

### 🎤 Keynote/Cue Card Mode
Presentation-ready cue cards in LaTeX format:
- 📇 Front/back card layout
- 🎨 Clean, professional styling
- 📱 Print-ready format

---

## 🏗️ Architecture

### Backend (`/backend`)

The backend is built with Python and follows an **agentic pipeline architecture**:

```
Documents → LLM Analysis → Knowledge Graph → Clustering → Ordering → Generation
```

#### Core Components

**1. Agents Pipeline** (`backend/agents/`)
- **LLM Analyzer**: Parses PDFs and extracts key topics using vision-enabled LLMs
- **Knowledge Graph Builder**: Constructs semantic relationships between concepts with intelligent source tracking
- **Clusterer**: Groups concepts by difficulty level for progressive learning
- **Orderer**: Optimizes concept sequence for learning flow
- **Generator**: Produces output in three formats (cheatsheet/flashcard/keynote)

**2. Document Processing** (`backend/agents/parser/`)
- PDF text extraction with OCR fallback
- Image embedding and LaTeX integration
- Page-level content tracking with metadata

**3. RAG System** (`backend/agents/rag/`)
- Knowledge graph construction for semantic search
- Corpus preparation and indexing
- Citation and source attribution

**4. Generation Engine** (`backend/agents/generation.py`)
- **Cheatsheet**: Multi-column LaTeX with difficulty-colored sections
- **Flashcard**: JSON format compatible with Anki/Quizlet
- **Keynote**: LaTeX cue cards with front/back layout
- **LLM-powered refinement**: Filters unimportant content and generates concise summaries

**5. Server & Workers** (`backend/server/`)
- FastAPI-based API server
- Background workers for LaTeX → PDF compilation
- Database layer for study session persistence

#### Key Technologies
- **LLMs**: OpenAI GPT-4o-mini for content analysis and refinement
- **Document Processing**: PyPDF2, pdfplumber for PDF parsing
- **RAG System**: Atlas-RAG for knowledge graph construction and semantic search
- **Database**: SQLite for study session persistence
- **API Framework**: FastAPI for high-performance REST endpoints
- **LaTeX**: Full LaTeX rendering pipeline with image support and PDF compilation

### Frontend (`/frontend`)

A modern React + TypeScript application built with Vite:

#### Features
- 📝 **Real-time LaTeX Editor**: Monaco-based editor with syntax highlighting
- 🔍 **Live PDF Preview**: Instant compilation and rendering
- 💬 **Integrated Chat**: AI assistance for content refinement
- 🎴 **Flashcard Interface**: Interactive flip-card study mode
- 📤 **Multi-format Upload**: Drag-and-drop support for PDF/images/text

#### Tech Stack
- **React 18** with TypeScript
- **Vite** for blazing-fast builds
- **SyncTeX** for LaTeX ↔ PDF coordinate mapping

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.12+**
- **Node.js 18+**
- **OpenAI API Key** (for LLM features)

### Backend Setup

```bash
# Navigate to project root
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
echo "OPENAI_API_KEY=your_key_here" > .env

# Run the pipeline test
python -m backend.agents.test_run \
  --grouped test_json/grouped.json \
  --job-id my_study_session \
  --output-format cheatsheet
```

### Frontend Setup

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will be available at `http://localhost:5173`

---

## 📖 Usage Examples

### Generate a Cheatsheet

```bash
python -m backend.agents.test_run \
  --grouped test_json/grouped.json \
  --job-id course_2024 \
  --output-format cheatsheet
```

Output: `course_2024/cheatsheet.tex` + `course_2024/generation_metadata.json`

### Generate Flashcards

```bash
python -m backend.agents.test_run \
  --grouped test_json/grouped.json \
  --job-id course_2024 \
  --output-format flashcard
```

Output: `course_2024/flashcard.json` with card metadata and source tracking

### Generate Keynote Cue Cards

```bash
python -m backend.agents.test_run \
  --grouped test_json/grouped.json \
  --job-id course_2024 \
  --output-format keynote
```

Output: `course_2024/keynote.tex` with printable front/back cards

---

## 🔧 Configuration

### Input Format (`test_json/grouped.json`)

```json
{
  "Lectures": ["path/to/lecture1.pdf", "path/to/lecture2.pdf"],
  "Tutorials": ["path/to/tutorial1.pdf"],
  "Labs": ["path/to/lab1.pdf"],
  "Miscellaneous": ["path/to/notes.pdf"]
}
```

### Generation Metadata

Each generation produces a `generation_metadata.json` that maps:
- **Cheatsheet**: Line ranges (`"50-55"`) → source page tuples `[("doc.pdf", 3)]`
- **Flashcard**: Card indices (`"0"`, `"1"`) → source page tuples
- **Keynote**: Card indices → source page tuples

This enables **citation tracking** and **source attribution** for every generated block.

---

## 🎯 Features

### ✅ Implemented

- [x] Multi-format PDF parsing with OCR fallback
- [x] LLM-powered knowledge graph construction
- [x] Intelligent difficulty-based clustering
- [x] Source tracking with page-level granularity
- [x] Three output formats (cheatsheet/flashcard/keynote)
- [x] LaTeX editor with real-time preview
- [x] Interactive flashcard study mode
- [x] Generation metadata for citation tracking

### 🚧 In Progress

- [ ] SyncTeX bidirectional navigation (LaTeX ↔ PDF)
- [ ] Chat panel for iterative refinement
- [ ] Flashcard analytics and spaced repetition

---

## 💥 Challenges We Ran Into

### PDF ↔ LaTeX Mappings
Sparse documentation meant months of work condensed into hours of exploratory trial and error to build a stable, reversible link between LaTeX source and rendered PDF coordinates. SyncTeX integration proved particularly tricky.

### Performance Juggling
Keeping the LaTeX editor, PDF renderer, and chat in sync without freezing the browser required careful worker threading and UI isolation. The compile → render → display cycle needed aggressive optimization.

### Rate Limits 😭
Novel solutions don't always mean feasible for production. At the end of the day, **deployment > theory**. We had to implement intelligent batching and caching to stay within API quotas.

---

## 🔮 What's Next

### Near-term Roadmap

1. **Strengthen LaTeX–PDF Round-trip Reliability**
   - Improve SyncTeX coordinate mapping
   - Add bidirectional navigation with visual indicators

2. **Smart AI Summarization**
   - Context-aware content filtering
   - User-controlled edits without unexpected rewrites
   - Preserve manual changes during regeneration

3. **Flashcard Analytics**
   - Track study performance per card
   - Implement spaced repetition algorithm
   - Better long-term memory retention

4. **Maybe... Sleep** 😴

### Long-term Vision

- Multi-language support beyond English
- Collaborative study sessions
- Mobile-optimized interface
- Export to Anki, Quizlet, Notion
- Voice-to-flashcard conversion

---

## 🤝 Contributing

This project is open to contributions! Whether you're:
- 🐛 Fixing bugs
- ✨ Adding features  
- 📝 Improving documentation
- 🎨 Enhancing the UI

...we'd love your help. Please open an issue or PR!

---

## 📄 License

This project is available under the MIT License. See `LICENSE` for details.

---

## 🙏 Acknowledgments

Built with caffeine, panic, and determination by students who've been there.

Special thanks to:
- The OpenAI team for GPT-4o-mini
- The LaTeX community for decades of typesetting excellence
- Every stressed student who's ever said "I should've started earlier"

---

## 📞 Support

Having issues? Found a bug? Want to share your success story?

- 📧 Open an issue on GitHub
- 💬 Join our Discord (coming soon!)
- 🐦 Tweet us your exam victories

---

<div align="center">

**Remember:** The best time to start studying was yesterday. The second best time is now.

*Now go ace that exam!* 🎓✨

</div>

