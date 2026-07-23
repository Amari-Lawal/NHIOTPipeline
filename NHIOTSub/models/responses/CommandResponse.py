from pydantic import BaseModel


class CommandResponse(BaseModel):
    result: str
    error: str
    function: str = ""
    stdout: str = ""
    stderr: str = ""

    @classmethod
    def from_stdout(cls, stdout: str, stderr: str) -> "CommandResponse":
        function, result = "", stdout

        if ":" in stdout:
            function, result = stdout.split(":", 1)
        elif ":" in stderr:
            function, _ = stderr.split(":", 1)

        return cls(
            result=result,
            error=stderr,
            function=function,
            stdout=stdout,
            stderr=stderr,
        )
