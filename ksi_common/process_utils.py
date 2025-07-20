"""Process management utilities extracted from completion service."""

import asyncio
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("process_utils")


class ProcessManager:
    """Manages async subprocess execution with proper cancellation and cleanup."""
    
    def __init__(self):
        self.active_processes: Dict[str, asyncio.subprocess.Process] = {}
        self.process_lock = asyncio.Lock()
    
    async def run_subprocess(
        self,
        cmd: List[str],
        process_id: str,
        working_dir: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        stdin_data: Optional[str] = None,
        timeout: int = 300,
        progress_timeout: int = 300
    ) -> Tuple[int, str, str]:
        """Run subprocess with proper tracking and cancellation support.
        
        Args:
            cmd: Command and arguments to execute
            process_id: Unique ID for tracking this process
            working_dir: Working directory for the process
            env: Environment variables (defaults to os.environ)
            stdin_data: Data to write to stdin
            timeout: Overall timeout in seconds
            progress_timeout: Timeout for no output in seconds
            
        Returns:
            Tuple of (returncode, stdout, stderr)
            
        Raises:
            asyncio.TimeoutError: If timeout exceeded
            asyncio.CancelledError: If cancelled
            subprocess.CalledProcessError: If process failed
        """
        if env is None:
            env = os.environ
        
        stdout_chunks = []
        stderr_chunks = []
        start_time = time.time()
        last_output_time = start_time
        
        async def read_stream_async(stream, chunks, stream_name):
            """Read from stream and collect chunks."""
            nonlocal last_output_time
            try:
                while True:
                    chunk = await stream.read(8192)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    last_output_time = time.time()
                    
                    # Log stderr for debugging
                    if stream_name == "stderr":
                        chunk_str = chunk.decode('utf-8', errors='replace')
                        if chunk_str.strip():
                            logger.debug(f"Process {process_id} stderr: {chunk_str.strip()}")
            except asyncio.CancelledError:
                pass  # Expected during cancellation
            except Exception as e:
                logger.error(f"Error reading {stream_name}: {e}")
        
        process = None
        try:
            # Start async subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE if stdin_data else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(working_dir) if working_dir else None,
                env=env
            )
            
            # Register process for cleanup on cancellation
            async with self.process_lock:
                self.active_processes[process_id] = process
            
            logger.info(f"Started process {process_id} (PID: {process.pid})")
            
            # Write stdin data if provided
            if stdin_data and process.stdin:
                try:
                    process.stdin.write(stdin_data.encode('utf-8'))
                    await process.stdin.drain()
                    process.stdin.close()
                    await process.stdin.wait_closed()
                except Exception as e:
                    logger.error(f"Failed to write stdin to process {process_id}: {e}")
            
            # Start async stream readers
            stdout_task = asyncio.create_task(
                read_stream_async(process.stdout, stdout_chunks, "stdout")
            )
            stderr_task = asyncio.create_task(
                read_stream_async(process.stderr, stderr_chunks, "stderr")
            )
            
            # Monitor progress and timeouts
            while process.returncode is None:
                current_time = time.time()
                elapsed = current_time - start_time
                
                # Check progress timeout
                time_since_output = current_time - last_output_time
                if time_since_output > progress_timeout:
                    logger.error(
                        f"Process {process_id} no output for {progress_timeout}s, killing",
                        elapsed=elapsed
                    )
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        process.kill()
                        await process.wait()
                    raise asyncio.TimeoutError(f"No progress for {progress_timeout}s")
                
                # Check overall timeout
                if elapsed > timeout:
                    logger.error(
                        f"Process {process_id} overall timeout {timeout}s exceeded",
                        elapsed=elapsed
                    )
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        process.kill()
                        await process.wait()
                    raise asyncio.TimeoutError(f"Overall timeout {timeout}s exceeded")
                
                await asyncio.sleep(1)
            
            # Wait for stream readers to complete
            try:
                await asyncio.wait_for(asyncio.gather(stdout_task, stderr_task), timeout=5)
            except asyncio.TimeoutError:
                logger.warning(f"Stream readers for process {process_id} timed out")
            
            # Combine output
            stdout = b''.join(stdout_chunks).decode('utf-8', errors='replace')
            stderr = b''.join(stderr_chunks).decode('utf-8', errors='replace')
            
            logger.info(
                f"Process {process_id} completed",
                returncode=process.returncode,
                elapsed=round(time.time() - start_time, 2)
            )
            
            if process.returncode != 0:
                logger.error(
                    f"Process {process_id} failed with code {process.returncode}",
                    stderr=stderr[:500]  # First 500 chars
                )
                raise ProcessExecutionError(
                    f"Process {process_id} failed with code {process.returncode}",
                    process.returncode,
                    stdout,
                    stderr
                )
            
            return process.returncode, stdout, stderr
            
        except asyncio.CancelledError:
            # Process cancellation - clean up subprocess
            if process and process.returncode is None:
                logger.info(f"Cancelling process {process_id}")
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
            raise
        except Exception:
            # Ensure process is terminated on any error
            if process and process.returncode is None:
                try:
                    process.terminate()
                    await asyncio.wait_for(process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
            raise
        finally:
            # Clean up process tracking
            async with self.process_lock:
                self.active_processes.pop(process_id, None)
    
    async def cancel_process(self, process_id: str) -> bool:
        """Cancel a specific process by ID.
        
        Args:
            process_id: ID of process to cancel
            
        Returns:
            True if process was found and cancelled, False if not found
        """
        async with self.process_lock:
            process = self.active_processes.get(process_id)
            if not process:
                return False
            
            if process.returncode is None:  # Still running
                logger.info(f"Cancelling process {process_id} (PID: {process.pid})")
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    logger.warning(f"Process {process_id} didn't terminate gracefully, killing")
                    process.kill()
                    await process.wait()
            
            return True
    
    async def cleanup_all_processes(self):
        """Clean up all active processes."""
        async with self.process_lock:
            for process_id, process in list(self.active_processes.items()):
                try:
                    if process.returncode is None:  # Still running
                        logger.warning(f"Killing process {process_id} (PID: {process.pid}) during cleanup")
                        process.terminate()
                        try:
                            await asyncio.wait_for(process.wait(), timeout=5)
                        except asyncio.TimeoutError:
                            process.kill()
                            await process.wait()
                except Exception as e:
                    logger.error(f"Error cleaning up process {process_id}: {e}")
            
            self.active_processes.clear()
    
    def get_active_processes(self) -> Dict[str, Dict[str, Any]]:
        """Get info about active processes."""
        result = {}
        for process_id, process in self.active_processes.items():
            result[process_id] = {
                "pid": process.pid,
                "returncode": process.returncode,
                "running": process.returncode is None
            }
        return result


class ProcessExecutionError(Exception):
    """Exception raised when a subprocess fails."""
    
    def __init__(self, message: str, returncode: int, stdout: str, stderr: str):
        super().__init__(message)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


# Global process manager instance
_process_manager: Optional[ProcessManager] = None


def get_process_manager() -> ProcessManager:
    """Get or create the global process manager."""
    global _process_manager
    if _process_manager is None:
        _process_manager = ProcessManager()
    return _process_manager


async def run_subprocess(
    cmd: List[str],
    process_id: str,
    **kwargs
) -> Tuple[int, str, str]:
    """Convenience function to run subprocess with global manager."""
    manager = get_process_manager()
    return await manager.run_subprocess(cmd, process_id, **kwargs)


async def cancel_process(process_id: str) -> bool:
    """Convenience function to cancel process with global manager."""
    manager = get_process_manager()
    return await manager.cancel_process(process_id)


async def cleanup_all_processes():
    """Convenience function to cleanup all processes."""
    manager = get_process_manager()
    await manager.cleanup_all_processes()