import os
import zipfile

def create_clean_archive(output_zip: str, root_dir: str):
    exclude_dirs = {
        ".venv", "venv", "__pycache__", ".pytest_cache", ".git",
        "chroma_data", ".idea", ".vscode"
    }
    exclude_files = {
        ".env", output_zip, "ai-sales-and-customer-service-agent.zip",
        "ai-sales-and-customer-service-agent-clean.zip"
    }
    exclude_extensions = {".pyc", ".pyo", ".pyd", ".log", ".zip"}

    print(f"Creating archive {output_zip} from {root_dir}...")
    file_count = 0
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for current_dir, dirs, files in os.walk(root_dir):
            # Prune excluded directories in place
            dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith(".")]

            for file in files:
                if file in exclude_files:
                    continue
                ext = os.path.splitext(file)[1].lower()
                if ext in exclude_extensions:
                    continue
                if file.startswith(".env") and file != ".env.example":
                    continue

                full_path = os.path.join(current_dir, file)
                rel_path = os.path.relpath(full_path, root_dir)
                zf.write(full_path, rel_path)
                file_count += 1

    print(f"Archive successfully created: {output_zip} ({file_count} files included).")

if __name__ == "__main__":
    archive_name = "ai-sales-and-customer-service-agent.zip"
    create_clean_archive(archive_name, ".")
    create_clean_archive("ai-sales-and-customer-service-agent-clean.zip", ".")
