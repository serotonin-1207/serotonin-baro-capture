using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;

[assembly: AssemblyTitle("Serotonin 바로캡처 Portable")]
[assembly: AssemblyDescription("설치 없이 실행하는 Serotonin 바로캡처")]
[assembly: AssemblyCompany("Serotonin")]
[assembly: AssemblyProduct("Serotonin 바로캡처")]
[assembly: AssemblyCopyright("이은호 · serotonin.1207@gmail.com")]
[assembly: AssemblyVersion("1.0.0.0")]
[assembly: AssemblyFileVersion("1.0.0.0")]

internal static class PortableLauncher
{
    [STAThread]
    private static int Main(string[] args)
    {
        string payloadPath = Path.Combine(
            Path.GetTempPath(),
            "SerotoninBaroCapture-1.0.0-" + Process.GetCurrentProcess().Id + ".exe"
        );

        try
        {
            using (Stream input = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload"))
            {
                if (input == null)
                    throw new InvalidOperationException("포터블 실행 파일에 앱 데이터가 없습니다.");
                using (FileStream output = new FileStream(payloadPath, FileMode.Create, FileAccess.Write, FileShare.None))
                    input.CopyTo(output);
            }

            ProcessStartInfo startInfo = new ProcessStartInfo(payloadPath, JoinArguments(args));
            startInfo.UseShellExecute = true;
            using (Process child = Process.Start(startInfo))
            {
                if (child == null)
                    return 1;
                child.WaitForExit();
                return child.ExitCode;
            }
        }
        catch (Exception error)
        {
            System.Windows.Forms.MessageBox.Show(
                "포터블 앱을 실행할 수 없습니다.\n" + error.Message,
                "Serotonin 바로캡처",
                System.Windows.Forms.MessageBoxButtons.OK,
                System.Windows.Forms.MessageBoxIcon.Error
            );
            return 1;
        }
        finally
        {
            try { if (File.Exists(payloadPath)) File.Delete(payloadPath); }
            catch { }
        }
    }

    private static string JoinArguments(string[] args)
    {
        StringBuilder result = new StringBuilder();
        foreach (string arg in args)
        {
            if (result.Length > 0) result.Append(' ');
            result.Append('"').Append(arg.Replace("\\", "\\\\").Replace("\"", "\\\"")).Append('"');
        }
        return result.ToString();
    }
}
