#!/usr/bin/env python3

import os, sys, glob

# constants
HOME = "/home/pokybuild3/yocto-worker/"
top_header = 7
max_cols = 11
cpu_hoggers = 5
zombie_proc_id = "<defunct>"
parser = "Parser"

# report the following whenever they occur
special_cmds = ["rm", "tar", "qemu"]

# string substitution to make things easier to read
subs = {
    "/home/pokybuild3/yocto-worker/" : "~/",
    "/build/build/tmp/work/" : "/...WORK_DIR.../"
}

def usage():
    print("Usage: " + sys.argv[0] + " <dest> <target>")

def list_top_outputs(logfile):
    # top delimiter
    top_start = "start: top output"
    top_end = "end: top output"

    # list of top outputs
    top_outputs = []

    # flag
    collect = False
    with open(logfile) as log:
        top_output = []
        for line in log:
            lstrip = line.strip()
            if collect:
                if lstrip.startswith(top_end):
                    collect = False
                    top_outputs.append(top_output)
                    top_output = []
                else:
                    top_output.append(lstrip)
            if lstrip.startswith(top_start):
                collect = True
                    
    return top_outputs

def summarize_top(top_outs, target):
    summaries = []
    kernel_summaries = []
    zombie_summaries = []
    short_summaries = []
    other_builds = []
    for top_out in top_outs:
        summary = {}
        kernel_summary = {}
        zombie_summary = {}
        short_summary = top_out[:top_header + cpu_hoggers]
        for line in top_out[top_header:]:
            cmd = line.split(maxsplit=max_cols)[-1]
            if cmd.startswith(HOME):
                b = cmd.split(HOME)[1].split("/")[0]
                if b not in other_builds:
                    other_builds.append(b)
            if cmd[0] == "[" and cmd[-1] == "]":    # kernel processes
                kproc = cmd[1:-1].split("/")[0]
                if kproc not in kernel_summary:
                    kernel_summary[kproc] = 1
                else:
                    kernel_summary[kproc] += 1
            elif zombie_proc_id in cmd:             # zombie processes
                zproc = cmd.split()[0][1:-1]
                if parser in zproc:
                    zproc = parser
                if zproc not in zombie_summary:
                    zombie_summary[zproc] = 1
                else:
                    zombie_summary[zproc] += 1
            else:                                   # userspace processes
                cmd_split = cmd.split()
                prog = cmd_split[0]
                if prog not in summary:
                    summary[prog] = 1
                else:
                    summary[prog] += 1
        summary = dict(sorted(summary.items(), key=lambda item: item[1], reverse=True))
        kernel_summary = dict(sorted(kernel_summary.items(), key=lambda item: item[1], reverse=True))
        zombie_summary = dict(sorted(zombie_summary.items(), key=lambda item: item[1], reverse=True))

        summaries.append(summary)
        kernel_summaries.append(kernel_summary)
        zombie_summaries.append(zombie_summary)
        short_summaries.append(short_summary)
    return (short_summaries, summaries, kernel_summaries, zombie_summaries, other_builds)
    
def summarize_path(path):
    sub = ["/recipe-sysroot-native/", "/../../libexec/", "/gcc/"]
    p = path
    for k, v in subs.items():
        p = p.replace(k, v)
    if all(x in p for x in sub):
        rsn_spl = p.split("/recipe-sysroot-native/")
        gcc_spl = rsn_spl[-1].split("/gcc/")
        p = rsn_spl[0] + "/...GCC.../" + gcc_spl[-1]
    
    return p

def write_summary(short_summary, summary, kernel_summary, zombie_summary, other_build, target, logfile):
    dirname = os.path.dirname(logfile)
    fname = os.path.basename(logfile)
    report_name = fname.split(".")[0] + "_summary.txt"
    outfile = os.path.join(dirname, report_name)
    out = "NOTE:\nProcesses that occur only once is not reported.\n"
    out += "Program names have been shortened for better readability.\n"
    out += "Substitutions are as follows:\n"
    for k, v in subs.items():
        out += (v + " = " + k + "\n")
    out += "\n"

    out += "top was invoked " + str(len(short_summary)) + " times.\n\n"
    out += "Current build: " + target + "\n"
    out += "Other builds:"
    for b in other_build:
        out += " " + b
    out += "\n\n"
    for i in range(len(short_summary)):
        for l in short_summary[i]:
            out += (l + "\n")

        out += ("\nUserspace Process Summary: " + "\n")
        if not summary:
            out += "There were no userspace processes\n"
        else:
            for k, v in summary[i].items():
                if v > 1 or any(k.startswith(x) for x in special_cmds):
                    r = summarize_path(k)
                    out += (str(v) + "  " + r + "\n")
        
        out += ("\nKernel Process Summary: " + "\n")
        if not kernel_summary:
            out += "There were no kernel processes\n"
        else:
            for k, v in kernel_summary[i].items():
                if v > 1 or any(k.startswith(x) for x in special_cmds):
                    out += (str(v) + "  " + k + "\n")

        out += ("\nZombie Process Summary: " + "\n")
        if not zombie_summary:
            out += "There were no zombie processes\n"
        else:
            for k, v in zombie_summary[i].items():
                if v > 1 or any(k.startswith(x) for x in special_cmds):
                    out += (str(v) + "  " + k + "\n")
        out += ("\n")

    with open(outfile, "w") as of:
        of.write(out)

def main():
    if len(sys.argv) != 3:
        usage()
        sys.exit()
        
    dest = sys.argv[1]
    target = sys.argv[2]
    host_data_dir = "intermittent_failure_host_data"
    directory = os.path.join(dest, target, host_data_dir)
    regs = (directory + "/*_top.txt", directory + "/*_failure_*.txt")
    for exts in regs:
        for f in glob.glob(exts):
            outputs = list_top_outputs(f)
            short_summary, summary, kernel_summary, zombie_summary, other_build = summarize_top(outputs, target)
            write_summary(short_summary, summary, kernel_summary, zombie_summary, other_build, target, f)

main()
