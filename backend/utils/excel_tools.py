import os
import json
import pandas as pd
import openpyxl
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from langchain_core.tools import tool
from datetime import datetime
import re
import logging

logger = logging.getLogger(__name__)


async def _get_session_file_path(filepath: str, session_id: str) -> str:
    """Convert filepath to session workspace path."""
    try:
        # Import here to avoid circular imports
        from services.session_manager import session_manager
        
        # Get session workspace path
        session = await session_manager.get_session(session_id)
        if not session:
            raise RuntimeError(f"Session '{session_id}' not found")
        
        session.ensure_workspace_exists()
        
        # If filepath is already absolute and within workspace, use as-is
        if os.path.isabs(filepath) and filepath.startswith(str(session.workspace_path)):
            return filepath
        
        # Otherwise, treat as relative to workspace
        return str(Path(session.workspace_path) / filepath)
    except Exception as e:
        logger.error(f"Error getting session file path: {e}")
        raise


def _read_excel_sheet(filepath: str, sheet_name: str, header_row: int = 0) -> pd.DataFrame:
    """Shared function to read Excel sheets consistently for both metadata and query tools."""
    try:
        # Use consistent pandas parameters for both metadata and query operations
        df = pd.read_excel(
            filepath, 
            sheet_name=sheet_name,
            # Ensure consistent behavior
            header=header_row,  # Use specified row as header
            index_col=None,  # Don't use any column as index
            na_values=['', 'NaN', 'nan', 'NULL', 'null'],  # Consistent NaN handling
            keep_default_na=True
        )
        return df
    except Exception as e:
        logger.error(f"Error reading Excel sheet '{sheet_name}' from '{filepath}': {e}")
        raise


def _analyze_sheet_structure(filepath: str, sheet_name: str) -> Dict[str, Any]:
    """Analyze Excel sheet structure - simplified to show only essential column information."""
    try:
        # Read the sheet using shared function to ensure consistency with query tool
        df = _read_excel_sheet(filepath, sheet_name)
        
        # Get basic dimensions
        row_count, col_count = df.shape
        
        # Extract column name to type mapping
        columns = {}
        for col in df.columns:
            col_data = df[col]
            
            # Determine data type
            dtype_str = str(col_data.dtype)
            if dtype_str.startswith('int'):
                data_type = 'integer'
            elif dtype_str.startswith('float'):
                data_type = 'float'
            elif dtype_str == 'bool':
                data_type = 'boolean'
            elif pd.api.types.is_datetime64_any_dtype(col_data):
                data_type = 'datetime'
            else:
                data_type = 'text'
            
            columns[str(col)] = data_type
        
        return {
            "dimensions": {"rows": row_count, "cols": col_count},
            "columns": columns,
            "column_names": list(columns.keys())
        }

    except Exception as e:
        logger.error(f"Error analyzing sheet structure: {e}")
        return {"error": str(e)}


async def excel_metadata_impl(filepaths: List[str], session_id: str) -> str:
    """Implementation for excel_metadata tool - supports batch operations."""
    try:
        results = {}
        
        for filepath in filepaths:
            try:
                full_path = await _get_session_file_path(filepath, session_id)
                
                if not os.path.exists(full_path):
                    results[filepath] = {"error": f"File '{filepath}' not found in session workspace"}
                    continue
                
                # Get file info
                file_stat = os.stat(full_path)
                file_size_mb = round(file_stat.st_size / (1024 * 1024), 2)
                
                # Get sheet names
                try:
                    excel_file = pd.ExcelFile(full_path)
                    sheet_names = excel_file.sheet_names
                except Exception as e:
                    results[filepath] = {"error": f"Error reading Excel file: {str(e)}"}
                    continue
                
                # Analyze each sheet
                sheets_info = {}
                for sheet_name in sheet_names:
                    try:
                        analysis = _analyze_sheet_structure(full_path, sheet_name)
                        sheets_info[sheet_name] = {
                            "dimensions": analysis["dimensions"],
                            "columns": analysis["columns"]
                        }
                    except Exception as e:
                        sheets_info[sheet_name] = {"error": str(e)}
                
                # Build simplified result
                results[filepath] = {
                    "file_info": {
                        "sheets": sheet_names,
                        "file_size": f"{file_size_mb}MB"
                    },
                    "sheets": sheets_info
                }
                
            except Exception as e:
                logger.error(f"Excel metadata analysis failed for {filepath}: {e}")
                results[filepath] = {"error": f"Error analyzing Excel file: {str(e)}"}
        
        return json.dumps(results, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"Excel metadata analysis failed: {e}")
        return f"Error analyzing Excel file(s): {str(e)}"


async def excel_query_impl(queries: List[Dict[str, Any]], session_id: str) -> str:
    """Implementation for excel_query tool - supports batch operations."""
    try:
        results = {}
        loaded_files = {}  # Cache loaded files to avoid re-reading
        
        for i, query_info in enumerate(queries):
            try:
                filepath = query_info["filepath"]
                sheet = query_info["sheet"]
                query_string = query_info["query_string"]
                header_row = query_info.get("header_row", 0)
                query_id = query_info.get("id", f"query_{i}")
                
                # Get or load the Excel file
                file_key = f"{filepath}|{sheet}|{header_row}"
                if file_key not in loaded_files:
                    full_path = await _get_session_file_path(filepath, session_id)
                    
                    if not os.path.exists(full_path):
                        results[query_id] = {"error": f"File '{filepath}' not found in session workspace"}
                        continue
                    
                    # Read Excel file using shared function
                    try:
                        df = _read_excel_sheet(full_path, sheet, header_row)
                        loaded_files[file_key] = df
                    except Exception as e:
                        results[query_id] = {"error": f"Error reading Excel sheet '{sheet}': {str(e)}"}
                        continue
                else:
                    df = loaded_files[file_key]
                
                # Execute query
                try:
                    # Create safe execution context
                    exec_context = {
                        "df": df, 
                        "pd": pd,
                        "__builtins__": {}
                    }
                    
                    # Handle different query types
                    if query_string.strip().startswith('df.'):
                        # Direct pandas operations like df.head(), df.groupby(), etc.
                        result = eval(query_string, exec_context)
                    else:
                        # Try pandas query syntax first
                        try:
                            result = df.query(query_string)
                        except Exception:
                            # If query syntax fails, try eval with df context
                            result = eval(query_string, exec_context)
                    
                    # Format result for output
                    if isinstance(result, pd.DataFrame):
                        if len(result) == 0:
                            output = "Query returned no results."
                        elif len(result) > 100:
                            # Truncate large results
                            output = f"Query returned {len(result)} rows (showing first 100):\n\n"
                            output += result.head(100).to_string(index=False)
                        else:
                            output = f"Query returned {len(result)} rows:\n\n"
                            output += result.to_string(index=False)
                    elif isinstance(result, pd.Series):
                        output = f"Query result:\n\n{result.to_string()}"
                    else:
                        output = f"Query result: {result}"
                    
                    results[query_id] = {
                        "filepath": filepath,
                        "sheet": sheet,
                        "query": query_string,
                        "result": output
                    }
                    
                except Exception as e:
                    results[query_id] = {
                        "filepath": filepath,
                        "sheet": sheet,
                        "query": query_string,
                        "error": f"Error executing query: {str(e)}\nMake sure to use 'df' to reference the dataframe, e.g., 'df.head()' or column names in quotes for query syntax."
                    }
            
            except Exception as e:
                query_id = query_info.get("id", f"query_{i}")
                results[query_id] = {"error": f"Error processing query: {str(e)}"}
        
        return json.dumps(results, ensure_ascii=False, indent=2)
    
    except Exception as e:
        logger.error(f"Excel batch query failed: {e}")
        return f"Error processing Excel queries: {str(e)}"



async def read_excel_impl(filepath: str, sheet: str, coordinates: str, session_id: str) -> str:
    """Implementation for read_excel tool."""
    try:
        full_path = await _get_session_file_path(filepath, session_id)
        
        if not os.path.exists(full_path):
            return f"Error: File '{filepath}' not found in session workspace"
        
        # Parse coordinates
        try:
            if ':' in coordinates:
                # Range format like A1:C5
                start_cell, end_cell = coordinates.split(':')
                
                # Read with openpyxl for precise cell access
                wb = openpyxl.load_workbook(full_path, data_only=True)
                ws = wb[sheet]
                
                # Get cell range
                cell_range = ws[coordinates]
                
                # Format output
                result_rows = []
                for row in cell_range:
                    if isinstance(row, tuple):
                        # Multiple cells in row
                        row_values = [str(cell.value) if cell.value is not None else "" for cell in row]
                        result_rows.append("\t".join(row_values))
                    else:
                        # Single cell
                        result_rows.append(str(row.value) if row.value is not None else "")
                
                return f"Excel range {coordinates} from sheet '{sheet}':\n\n" + "\n".join(result_rows)
                
            elif coordinates.isdigit() or ':' in coordinates and all(part.isdigit() for part in coordinates.split(':')):
                # Row number format like "1" or "1:5"
                if ':' in coordinates:
                    start_row, end_row = map(int, coordinates.split(':'))
                    df = pd.read_excel(full_path, sheet_name=sheet, header=None, skiprows=start_row-1, nrows=end_row-start_row+1)
                else:
                    row_num = int(coordinates)
                    df = pd.read_excel(full_path, sheet_name=sheet, header=None, skiprows=row_num-1, nrows=1)
                
                return f"Excel rows {coordinates} from sheet '{sheet}':\n\n" + df.to_string(index=False, header=False)
            
            else:
                return f"Error: Invalid coordinate format '{coordinates}'. Use formats like 'A1:C5', '1:3', or '1'"
        
        except Exception as e:
            return f"Error reading Excel coordinates '{coordinates}': {str(e)}"
    
    except Exception as e:
        logger.error(f"Read Excel failed: {e}")
        return f"Error reading Excel file: {str(e)}"


def create_excel_metadata_tool(session_id: str):
    """Create excel_metadata tool bound to a specific session."""
    @tool
    async def excel_metadata(filepaths: List[str]) -> str:
        """
        Get Excel file metadata showing available sheets and column names.
        Supports batch operations for multiple files.

        Args:
            filepaths: List of paths to Excel files (relative to session workspace)

        Returns:
            JSON with sheet names and column names for each file
        """
        return await excel_metadata_impl(filepaths, session_id)
    
    return excel_metadata


def create_excel_query_tool(session_id: str):
    """Create excel_query tool bound to a specific session."""
    @tool
    async def excel_query(queries: List[Dict[str, Any]]) -> str:
        """
        Execute pandas queries on Excel sheets. Supports batch operations.
        Use excel_metadata first to see available columns.
        
        Args:
            queries: List of query dictionaries, each containing:
                - filepath: Path to the Excel file (relative to session workspace)
                - sheet: Name of the sheet to query
                - query_string: Either:
                    - Pandas query syntax: "column > 5" or "name == 'value'"
                    - Direct df operations: "df.head()" or "df.groupby('col').sum()"
                - header_row: Row number to use as column headers (default: 0)
                - id: Optional identifier for the query (default: query_N)
            
        Returns:
            JSON with formatted query results for each query
        """
        return await excel_query_impl(queries, session_id)
    
    return excel_query




def create_read_excel_tool(session_id: str):
    """Create read_excel tool bound to a specific session."""
    @tool
    async def read_excel(filepath: str, sheet: str, coordinates: str) -> str:
        """
        Manual fallback for specific cell ranges when auto-parsing fails.
        
        Provides raw cell value inspection and handles merged cells appropriately.
        Critical fallback when excel_metadata auto-detection fails.
        
        Args:
            filepath: Path to the Excel file (relative to session workspace)
            sheet: Name of the sheet to read
            coordinates: Cell coordinates (e.g., "A1:C5", "1:3", or "1")
        
        Returns:
            Raw cell values from the specified coordinates
        """
        return await read_excel_impl(filepath, sheet, coordinates, session_id)
    
    return read_excel


async def get_excel_tools(session_id: str):
    """Get all Excel tools for a specific session."""
    return [
        create_excel_metadata_tool(session_id),
        create_excel_query_tool(session_id),
        create_read_excel_tool(session_id)
    ]