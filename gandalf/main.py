import argparse
import asyncio

from typing import Any, Dict  # noqa

from gandalf.linters import checkstyle, mypy, pylint, swiftlint
from gandalf.reporters import github_reporter
from gandalf.project import sync_handler
from gandalf.storage.git_storage_engine import GitNotesStorageEngine

REPORTERS = {
    'github': github_reporter,
}  # type: Dict[str, Any]

LINTERS = {
    'mypy': mypy,
    'pylint': pylint,
    'swiftlint': swiftlint,
    'checkstyle': checkstyle,
}  # type: Dict[str, Any]


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument('--reporter', type=str, nargs='+', default=['github'],
                        help='The reporter to use when reporting errors.')
    parser.add_argument('--linter', type=str, required=True,
                        help='The type of lint file to parse.')
    parser.add_argument('--store_problems', default=False, action='store_true',
                        help='Whether or not to store lint errors as git '
                             'notes and filter out problems')
    parser.add_argument('files', type=str, nargs='+',
                        help='The lint file being parsed.')
    for name, reporter in REPORTERS.items():
        reporter.register_arguments(parser)
    return parser


async def run_loop(args):
    reporters = []
    for reporter in args.reporter:
        if reporter not in REPORTERS:
            raise Exception('Reporter {} is invalid, options are {}'.format(
                reporter, ','.join(list(REPORTERS.keys()))
            ))
        reporters.append(REPORTERS[reporter].create_reporter(args))

    problems = set()
    if args.linter not in LINTERS:
        raise Exception('Linter {} is invalid, options are {}'.format(
            args.linter, ','.join(list(LINTERS.keys()))
        ))
    linter = LINTERS[args.linter]
    for lint_file_path in args.files:
        with open(lint_file_path, 'r') as lint_file:
            problems.update(linter.parse(lint_file.read()))

    storage_engine = GitNotesStorageEngine('origin')

    awaitable_array = []

    if args.store_problems:
        awaitable_array.append(storage_engine.store_problems(problems))
        existing_problems = await storage_engine.get_existing_problems()
        problems = problems.difference(existing_problems)

    awaitable_array.extend([reporter.report(problems) for
                            reporter in
                            reporters])
    await asyncio.gather(*awaitable_array)


def main(fork_from: str, from_sha: str, repo_name: str, ticket_id: int,
         pr_url: str, linter: str ='pylint', reporter: str ='github'):

    output_path = sync_handler(
        fork_from, from_sha, repo_name, ticket_id, pr_url)
    args = create_parser().parse_args([
        '--linter', linter, '--reporter', reporter,
        '--commit', from_sha, '--pr_url', pr_url,
        output_path
    ])

    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_loop(args))
    loop.close()


if __name__ == '__main__':
    main()
