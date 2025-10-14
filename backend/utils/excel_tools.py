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


def _is_csv_file(filepath: str) -> bool:
    """Determine if the provided file path points to a CSV file."""
    return Path(filepath).suffix.lower() == ".csv"


def _column_letters_to_index(column_letters: str) -> int:
    """Convert Excel-style column letters (e.g., 'A', 'AA') to a zero-based index."""
    index = 0
    for char in column_letters.upper():
        if not 'A' <= char <= 'Z':
            raise ValueError(f"Invalid column letter '{char}' in reference '{column_letters}'")
        index = index * 26 + (ord(char) - ord('A') + 1)
    return index - 1


def _parse_cell_reference(cell_ref: str) -> Optional[tuple]:
    """Parse Excel-style cell reference (e.g., 'A1') into zero-based row and column indices."""
    match = re.match(r'^([A-Za-z]+)(\d+)$', cell_ref.strip())
    if not match:
        return None
    column_letters, row_number = match.groups()
    row_index = int(row_number) - 1
    column_index = _column_letters_to_index(column_letters)
    if row_index < 0 or column_index < 0:
        return None
    return row_index, column_index


def _read_excel_sheet(filepath: str, sheet_name: Optional[str], header_row: int = 0) -> pd.DataFrame:
    """Shared function to read spreadsheet data consistently for both metadata and query tools."""
    try:
        if _is_csv_file(filepath):
            df = pd.read_csv(
                filepath,
                header=header_row if header_row is not None else None,
                index_col=None,
                na_values=['', 'NaN', 'nan', 'NULL', 'null'],
                keep_default_na=True
            )
        else:
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
        location = f"sheet '{sheet_name}'" if sheet_name else "file"
        logger.error(f"Error reading tabular data ({location}) from '{filepath}': {e}")
        raise


def _analyze_sheet_structure(filepath: str, sheet_name: Optional[str]) -> Dict[str, Any]:
    """Analyze spreadsheet structure - simplified to show only essential column information."""
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
                
                is_csv = _is_csv_file(full_path)

                # Get sheet names
                try:
                    if is_csv:
                        sheet_names = ["CSV"]
                    else:
                        excel_file = pd.ExcelFile(full_path)
                        sheet_names = excel_file.sheet_names
                except Exception as e:
                    results[filepath] = {"error": f"Error reading file: {str(e)}"}
                    continue
                
                # Analyze each sheet
                sheets_info = {}
                for sheet_name in sheet_names:
                    try:
                        analysis = _analyze_sheet_structure(full_path, None if is_csv else sheet_name)
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
                        "file_size": f"{file_size_mb}MB",
                        "file_type": "csv" if is_csv else "excel"
                    },
                    "sheets": sheets_info
                }
                
            except Exception as e:
                logger.error(f"Spreadsheet metadata analysis failed for {filepath}: {e}")
                results[filepath] = {"error": f"Error analyzing file: {str(e)}"}
        
        return json.dumps(results, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"Spreadsheet metadata analysis failed: {e}")
        return f"Error analyzing spreadsheet file(s): {str(e)}"


async def _excel_query_impl(filepath: str, sheet: str, query_string: str, session_id: str, header_row: int = 0) -> str:
    """Implementation for excel_query tool."""
    try:
        full_path = await _get_session_file_path(filepath, session_id)
        
        if not os.path.exists(full_path):
            return f"Error: File '{filepath}' not found in session workspace"
        
        is_csv = _is_csv_file(full_path)

        # Read Excel/CSV file
        try:
            df = _read_excel_sheet(full_path, None if is_csv else sheet, header_row)
        except Exception as e:
            target = "CSV file" if is_csv else f"Excel sheet '{sheet}'"
            return f"Error reading {target}: {str(e)}"
        
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
        logger.error(f"Spreadsheet query failed: {e}")
        return f"Error processing spreadsheet query: {str(e)}"



async def _read_excel_impl(filepath: str, sheet: str, coordinates: str, session_id: str) -> str:
    """Implementation for read_excel tool."""
    try:
        full_path = await _get_session_file_path(filepath, session_id)
        
        if not os.path.exists(full_path):
            return f"Error: File '{filepath}' not found in session workspace"
        
        is_csv = _is_csv_file(full_path)

        # Parse coordinates
        try:
            if is_csv:
                df = pd.read_csv(full_path, header=None)
                coordinate_str = coordinates.strip()

                if ':' in coordinate_str and re.match(r'^[A-Za-z]+\d+:[A-Za-z]+\d+$', coordinate_str):
                    start_cell, end_cell = coordinate_str.split(':')
                    start_indices = _parse_cell_reference(start_cell)
                    end_indices = _parse_cell_reference(end_cell)
                    if not start_indices or not end_indices:
                        return f"Error: Invalid coordinate format '{coordinates}'. Use formats like 'A1:C5', '1:3', or '1'"

                    start_row, start_col = start_indices
                    end_row, end_col = end_indices
                    subset = df.iloc[start_row:end_row+1, start_col:end_col+1].fillna("")
                    result_rows = ["\t".join(map(str, row.tolist())) for _, row in subset.iterrows()]
                    result_output = f"CSV range {coordinates}:\n\n" + "\n".join(result_rows)

                elif coordinate_str.isdigit() or (':' in coordinate_str and all(part.isdigit() for part in coordinate_str.split(':'))):
                    if ':' in coordinate_str:
                        start_row, end_row = map(int, coordinate_str.split(':'))
                        subset = df.iloc[start_row-1:end_row].fillna("")
                        label = f"CSV rows {coordinates}"
                    else:
                        row_num = int(coordinate_str)
                        subset = df.iloc[[row_num-1]].fillna("")
                        label = f"CSV row {coordinates}"
                    result_output = f"{label}:\n\n" + subset.to_string(index=False, header=False)

                else:
                    return f"Error: Invalid coordinate format '{coordinates}'. Use formats like 'A1:C5', '1:3', or '1'"

                # Check token count using universal token checker
                from services.session_manager import check_token_limit
                is_within_limit, token_count, error_message = check_token_limit(result_output, max_tokens=7000)
                if not is_within_limit:
                    return error_message

                return result_output

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
            return f"Error reading tabular coordinates '{coordinates}': {str(e)}"
    
    except Exception as e:
        logger.error(f"Read spreadsheet failed: {e}")
        return f"Error reading spreadsheet file: {str(e)}"


@tool
async def excel_metadata(
    filepaths: List[str],
    config: Annotated[RunnableConfig, InjectedToolArg]
) -> str:
    """
    Get spreadsheet metadata showing available sheets and column names.
    Supports Excel workbooks (.xls, .xlsx) and CSV files (exposed as a single sheet named "CSV").
    Supports batch operations for multiple files.

    Args:
        filepaths: List of paths to Excel or CSV files (relative to session workspace)

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
    Execute arbitrary pandas code on spreadsheet data (Excel or CSV). Use excel_metadata first to see available columns.

    The dataframe is available as 'df', pandas as 'pd', and numpy as 'np'.
    You must write results to the 'context' dictionary using context['key'] = 'value'.
    All context values must be strings.

    Args:
        filepath: Path to the Excel or CSV file (relative to session workspace)
        sheet: Name of the sheet to query (use "CSV" for CSV files)
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

    Supports Excel workbooks and CSV files. Provides raw cell value inspection,
    handles merged cells appropriately for Excel, and lets you reference CSV data
    using Excel-style coordinates (e.g., "A1:C5") or row ranges.
    Critical fallback when excel_metadata auto-detection fails.

    Args:
        filepath: Path to the Excel or CSV file (relative to session workspace)
        sheet: Name of the sheet to read (ignored for CSV files)
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
