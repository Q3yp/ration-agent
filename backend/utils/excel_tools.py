import os
import json
import pandas as pd
import openpyxl
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Annotated
from langchain_core.tools import tool, InjectedToolArg
from langchain_core.runnables import RunnableConfig
from datetime import datetime
import re
import logging
logger = logging.getLogger(__name__)


async def _get_session_file_path(filepath: str, session_id: str) -> str:
    """Convert filepath to session workspace path."""
    try:
        # Import here to avoid circular imports
        from services.session_manager import session_manager
        
        # Get session workspace path using shared utility
        workspace_path = await session_manager.get_session_workspace_path(session_id)
        
        # If filepath is already absolute and within workspace, use as-is
        if os.path.isabs(filepath) and filepath.startswith(str(workspace_path)):
            return filepath
        
        # Otherwise, treat as relative to workspace
        return str(workspace_path / filepath)
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


async def _excel_metadata_impl(filepaths: List[str], session_id: str) -> str:
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


async def _excel_query_impl(filepath: str, sheet: str, query_string: str, session_id: str, header_row: int = 0) -> str:
    """Implementation for excel_query tool."""
    try:
        full_path = await _get_session_file_path(filepath, session_id)
        
        if not os.path.exists(full_path):
            return f"Error: File '{filepath}' not found in session workspace"
        
        # Read Excel file
        try:
            df = _read_excel_sheet(full_path, sheet, header_row)
        except Exception as e:
            return f"Error reading Excel sheet '{sheet}': {str(e)}"
        
        # Execute query
        try:
            # Create execution context with common imports
            import numpy as np
            global_context = {
                "df": df, 
                "pd": pd,
                "np": np,
            }
            
            # Create context dict for LLM to write results (string:string)
            context = {}
            global_context["context"] = context
            
            # Execute arbitrary pandas code
            exec(query_string, global_context)
            
            # Format results from context dict
            if not context:
                return "No results were written to the context dictionary. Use context['key'] = 'value' to store results."
            
            # Format output from context
            output_lines = []
            for key, value in context.items():
                output_lines.append(f"{key}: {value}")
            
            formatted_output = "\n".join(output_lines)
            
            # Check token count using universal token checker
            from services.session_manager import check_token_limit
            is_within_limit, token_count, error_message = check_token_limit(formatted_output, max_tokens=7000)
            
            if not is_within_limit:
                return error_message
            
            return formatted_output
            
        except Exception as e:
            return f"Error executing code: {str(e)}\nUse 'df' to reference the dataframe and 'context' dict to store results. Example: context['result'] = str(df.head())"
    
    except Exception as e:
        logger.error(f"Excel query failed: {e}")
        return f"Error processing Excel query: {str(e)}"



async def _read_excel_impl(filepath: str, sheet: str, coordinates: str, session_id: str) -> str:
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
                
                result_output = f"Excel range {coordinates} from sheet '{sheet}':\n\n" + "\n".join(result_rows)
                
                # Check token count using universal token checker
                from services.session_manager import check_token_limit
                is_within_limit, token_count, error_message = check_token_limit(result_output, max_tokens=7000)
                
                if not is_within_limit:
                    return error_message
                
                return result_output
                
            elif coordinates.isdigit() or ':' in coordinates and all(part.isdigit() for part in coordinates.split(':')):
                # Row number format like "1" or "1:5"
                if ':' in coordinates:
                    start_row, end_row = map(int, coordinates.split(':'))
                    df = pd.read_excel(full_path, sheet_name=sheet, header=None, skiprows=start_row-1, nrows=end_row-start_row+1)
                else:
                    row_num = int(coordinates)
                    df = pd.read_excel(full_path, sheet_name=sheet, header=None, skiprows=row_num-1, nrows=1)
                
                result_output = f"Excel rows {coordinates} from sheet '{sheet}':\n\n" + df.to_string(index=False, header=False)
                
                # Check token count using universal token checker
                from services.session_manager import check_token_limit
                is_within_limit, token_count, error_message = check_token_limit(result_output, max_tokens=7000)
                
                if not is_within_limit:
                    return error_message
                
                return result_output
            
            else:
                return f"Error: Invalid coordinate format '{coordinates}'. Use formats like 'A1:C5', '1:3', or '1'"
        
        except Exception as e:
            return f"Error reading Excel coordinates '{coordinates}': {str(e)}"
    
    except Exception as e:
        logger.error(f"Read Excel failed: {e}")
        return f"Error reading Excel file: {str(e)}"


@tool
async def excel_metadata(
    filepaths: List[str],
    config: Annotated[RunnableConfig, InjectedToolArg]
) -> str:
    """
    Get Excel file metadata showing available sheets and column names.
    Supports batch operations for multiple files.

    Args:
        filepaths: List of paths to Excel files (relative to session workspace)

    Returns:
        JSON with sheet names and column names for each file
    """
    session_id = config["configurable"]["thread_id"]
    return await _excel_metadata_impl(filepaths, session_id)


@tool
async def excel_query(
    filepath: str,
    sheet: str,
    query_string: str,
    header_row: int = 0,
    config: Annotated[RunnableConfig, InjectedToolArg] = None
) -> str:
    """
    Execute arbitrary pandas code on Excel data. Use excel_metadata first to see available columns.

    The dataframe is available as 'df', pandas as 'pd', and numpy as 'np'.
    You must write results to the 'context' dictionary using context['key'] = 'value'.
    All context values must be strings.

    Args:
        filepath: Path to the Excel file (relative to session workspace)
        sheet: Name of the sheet to query
        query_string: Python code to execute. Must write results to context dict.
            Examples:
            - context['summary'] = str(df.describe())
            - context['row_count'] = str(len(df))
            - filtered = df[df['column'] > 5]; context['filtered'] = filtered.to_string()
        header_row: Row number to use as column headers (default: 0)

    Returns:
        Formatted results from context dictionary, or token limit message if exceeded. The limit is 7000 token.
    """
    session_id = config["configurable"]["thread_id"]
    return await _excel_query_impl(filepath, sheet, query_string, session_id, header_row)


@tool
async def read_excel(
    filepath: str,
    sheet: str,
    coordinates: str,
    config: Annotated[RunnableConfig, InjectedToolArg]
) -> str:
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
    session_id = config["configurable"]["thread_id"]
    return await _read_excel_impl(filepath, sheet, coordinates, session_id)


def get_excel_tools():
    """Get all Excel tools."""
    return [
        excel_metadata,
        excel_query,
        read_excel
    ]